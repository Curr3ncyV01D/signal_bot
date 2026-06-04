import logging
import asyncio
from datetime import datetime, timezone, timedelta
from src.core.config import config
from src.database.crud.user_service import get_active_users
from src.bot.notifier import send_liquidation_alert
from src.services.indicators.rsi import rsi_indicator

logger = logging.getLogger(__name__)

# Память алертов для анти-спама
user_alert_history = {}

async def process_liquidation_item(
    session, 
    symbol: str, 
    side_label: str, 
    bot, 
    liq_aggregator, 
    market_aggregator, 
    trade_aggregator
):
    """Принимает решение об отправке уведомления и выполняет рассылку через gather"""
    
    # 1. Мгновенно получаем всю статистику из оперативной памяти
    sum_5m, sum_1h, sum_cas, count_cas = liq_aggregator.get_metrics(symbol, side_label)
    m_data = market_aggregator.get_market_data(symbol, window_minutes=5)
    
    # CVD метрики
    _, _, delta_5m = trade_aggregator.get_cvd_metrics(symbol, minutes=5)
    _, _, delta_30m = trade_aggregator.get_cvd_metrics(symbol, minutes=30)
    
    # 2. Получаем активных юзеров из базы
    users = await get_active_users(session)
    
    # Список задач на отправку
    alert_tasks = []

    for user in users:
        payload = _check_user_triggers(
            user=user,
            symbol=symbol,
            side_label=side_label,
            sum_5m=sum_5m,
            sum_1h=sum_1h,
            sum_cas=sum_cas,
            count_cas=count_cas,
            m_data=m_data,
            delta_5m=delta_5m,
            delta_30m=delta_30m,
            market_aggregator=market_aggregator
        )
        
        if payload:
            alert_tasks.append(send_liquidation_alert(bot, user.id, **payload))

    # Массовая отправка алертов (внутри send_liquidation_alert уже есть семафор и throttling)
    if alert_tasks:
        await asyncio.gather(*alert_tasks, return_exceptions=True)

def _check_user_triggers(
    user, symbol, side_label, sum_5m, sum_1h, sum_cas, count_cas, 
    m_data, delta_5m, delta_30m, market_aggregator
):
    """Вынесенная логика проверки условий для конкретного юзера"""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    
    # --- 1. ТРИГГЕРЫ (Базовые условия пробития порогов) ---
    is_cascade = (count_cas >= config.CASCADE_TRIGGER_COUNT and 
                sum_cas >= user.threshold_cascade)
    
    is_vol_5m = sum_5m >= user.threshold
    is_vol_1h = sum_1h >= (user.threshold * config.VOLUME_MULTIPLIER)
    
    is_oi_pump = False
    if m_data and user.alert_oi:
        if m_data['oi_change_pct'] is not None and m_data['oi_change_value'] is not None:
            if (m_data['oi_change_pct'] >= user.threshold_oi_percent and 
                abs(m_data['oi_change_value']) >= user.threshold_oi_value):
                is_oi_pump = True

    # Если ни один порог не пробит — мгновенно скипаем юзера
    if not (is_cascade or is_vol_5m or is_vol_1h or is_oi_pump):
        return None

    # --- 2. ОПРЕДЕЛЕНИЕ ТИПА (Для заголовка и фильтров юзера) ---
    if is_cascade:
        alert_type = "CASCADE"
        alert_title = f"⚡️ LIQ КАСКАД x{count_cas}"
        is_allowed = user.alert_cascade
    elif is_oi_pump:
        alert_type = "OI_PUMP"
        alert_title = "📈 OI PUMP"
        is_allowed = user.alert_oi
    elif sum_5m > (sum_1h * config.SQUEEZE_RATIO):
        alert_type = "SQUEEZE"
        alert_title = "🔥 QUICK SQUEEZE"
        is_allowed = user.alert_squeeze
    else:
        alert_type = "VOLUME"
        alert_title = "📊 LIQ VOLUME"
        is_allowed = user.alert_volume

    # --- 3. ФИЛЬТРАЦИЯ ПО НАСТРОЙКАМ ---
    if not is_allowed:
        return None

    # --- 4. АНТИ-СПАМ (Smart Threshold) ---
    history_key = (user.id, symbol, side_label)
    last_alert = user_alert_history.get(history_key)

    if last_alert:
        if (now - last_alert['time']).total_seconds() < config.GLOBAL_COOLDOWN_SEC:
            return None
            
        if alert_type not in ["CASCADE", "OI_PUMP"]:
            grew_5m = sum_5m >= last_alert['sum_5m'] * config.ALERT_GROWTH_PERCENTAGE
            if not grew_5m:
                return None

    # --- 5. МГНОВЕННЫЙ ЛОКАЛЬНЫЙ РАСЧЕТ RSI (БЕЗ СЕТИ!) ---
    rsi_val = None
    if user.alert_rsi:
        # Забираем историю цен из агрегатора
        local_prices = list(market_aggregator.rsi_prices.get(symbol, []))
        # Считаем RSI локально в процессоре
        rsi_val = rsi_indicator.calculate_rsi_local(local_prices, config.RSI_PERIOD)

    # --- 6. ФОРМИРОВАНИЕ ПЕЙЛОАДА ---
    user_alert_history[history_key] = {
        'time': now,
        'sum_5m': sum_5m
    }
    
    return {
        "symbol": symbol,
        "side_label": side_label,
        "alert_title": alert_title,
        "alert_type": alert_type,
        "sum_5m": sum_5m,
        "sum_1h": sum_1h,
        "sum_cascade": sum_cas,
        "cascade_count": count_cas,
        "threshold_cascade": user.threshold_cascade,
        "oi_pct": m_data['oi_change_pct'] if m_data else None,
        "oi_val": m_data['oi_change_value'] if m_data else 0.0,
        "price_pct": m_data['price_change_pct'] if m_data else None,
        "total_oi": m_data['oi'] if m_data else 0.0,
        "funding": m_data['funding'] if m_data else 0.0,
        "delta_5m": delta_5m,
        "delta_30m": delta_30m,
        "rsi": rsi_val,
        "show_oi": user.alert_oi,
        "show_cvd": user.alert_cvd,
        "show_rsi": user.alert_rsi
    }

async def cleanup_alert_history_task():
    """Фоновая задача для очистки истории алертов (защита от утечки памяти)"""
    while True:
        await asyncio.sleep(3600)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        threshold = now - timedelta(hours=24)
        
        keys_to_delete = [
            key for key, data in user_alert_history.items() 
            if data['time'] < threshold
        ]
        
        for key in keys_to_delete:
            del user_alert_history[key]
            
        if keys_to_delete:
            logger.info(f"Очистка памяти: удалено {len(keys_to_delete)} старых записей из истории алертов.")