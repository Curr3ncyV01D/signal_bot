import logging
import asyncio
from datetime import datetime, timezone, timedelta
from src.core.config import config
from src.database.crud.user_service import get_active_users
from src.bot.notifier import send_liquidation_alert
from src.services.indicators.rsi import RSIIndicator

logger = logging.getLogger(__name__)

# Память алертов для анти-спама: { (user_id, symbol, side): {time, sum_5m} }
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
    """
    Главный мозг системы. Собирает данные из всех агрегаторов, 
    проверяет триггеры и принимает решение об отправке.
    """
    
    # 1. Сбор метрик из всех источников ОЗУ
    sum_5m, sum_1h, sum_cas, count_cas = liq_aggregator.get_metrics(symbol, side_label)
    m_data = market_aggregator.get_market_data(symbol, window_minutes=5)
    buy_5m, sell_5m, delta_5m = trade_aggregator.get_cvd_metrics(symbol, minutes=5)
    buy_30m, sell_30m, delta_30m = trade_aggregator.get_cvd_metrics(symbol, minutes=30)
    
    # 2. Получаем список активных пользователей
    users = await get_active_users(session)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    for user in users:
        # --- ШАГ 1: ПРОВЕРКА ТРИГГЕРОВ (Есть ли повод для сигнала?) ---
        
        # Триггер Каскада (Количество + Личный порог суммы каскада)
        is_cascade_trigger = (count_cas >= config.CASCADE_TRIGGER_COUNT and 
                             sum_cas >= user.threshold_cascade)
        
        # Триггеры объема (5м или 1ч)
        is_vol_5m_trigger = sum_5m >= user.threshold
        is_vol_1h_trigger = sum_1h >= (user.threshold * config.VOLUME_MULTIPLIER)

        # Триггер ОИ (Stage 2)
        is_oi_trigger = False
        if m_data and user.alert_oi:
            # Проверяем пробитие по % И по объему в $ одновременно
            if (m_data['oi_change_pct'] >= user.threshold_oi_percent and 
                abs(m_data['oi_change_value']) >= user.threshold_oi_value):
                is_oi_trigger = True

        # Если ни один порог не пробит — идем к следующему юзеру
        if not (is_cascade_trigger or is_vol_5m_trigger or is_vol_1h_trigger or is_oi_trigger):
            continue

        # --- ШАГ 2: ОПРЕДЕЛЕНИЕ ТИПА И ФИЛЬТРАЦИЯ ---
        # Устанавливаем приоритет: Cascade > OI > Squeeze > Volume
        if is_cascade_trigger:
            alert_type = "CASCADE"
            alert_title = f"⚡️ LIQ КАСКАД x{count_cas}"
            is_allowed = user.alert_cascade
        elif is_oi_trigger:
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

        if not is_allowed:
            continue

        # --- ШАГ 3: АНТИ-СПАМ (Smart Threshold / High Water Mark) ---
        history_key = (user.id, symbol, side_label)
        last_alert = user_alert_history.get(history_key)

        if last_alert:
            # Глобальный кулдаун
            if (now - last_alert['time']).total_seconds() < config.GLOBAL_COOLDOWN_SEC:
                continue
                
            # Если это не каскад и не ОИ, то сумма 5м должна вырасти на X% от прошлого алерта
            if alert_type not in ["CASCADE", "OI_PUMP"]:
                grew_enough = sum_5m >= last_alert['sum_5m'] * config.ALERT_GROWTH_PERCENTAGE
                if not grew_enough:
                    continue

        # --- ШАГ 4: ОБОГАЩЕНИЕ ДАННЫМИ (RSI) ---
        rsi_val = None
        if user.alert_rsi:
            rsi_val = await RSIIndicator().fetch_rsi(symbol=symbol)

        # --- ШАГ 5: ФИНАЛИЗАЦИЯ И ОТПРАВКА ---
        user_alert_history[history_key] = {
            'time': now,
            'sum_5m': sum_5m
        }

        await send_liquidation_alert(
            bot=bot,
            user_id=user.id,
            symbol=symbol,
            side_label=side_label,
            alert_title=alert_title,
            # Данные ликвидаций
            sum_5m=sum_5m,
            sum_1h=sum_1h,
            sum_cascade=sum_cas,
            cascade_count=count_cas,
            alert_type=alert_type,
            # Данные рынка (Stage 2)
            oi_pct=m_data['oi_change_pct'] if m_data else 0,
            oi_val=m_data['oi_change_value'] if m_data else 0,
            price_pct=m_data['price_change_pct'] if m_data else 0,
            total_oi=m_data['oi'] if m_data else 0,
            funding=m_data['funding'] if m_data else 0,
            # Данные дельты (CVD)
            delta_5m=delta_5m,
            delta_30m=delta_30m,
            # RSI
            rsi=rsi_val
        )

async def cleanup_alert_history_task():
    """Фоновая задача для очистки истории алертов (раз в час)"""
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
            logger.info(f"Очистка истории алертов: удалено {len(keys_to_delete)} записей.")