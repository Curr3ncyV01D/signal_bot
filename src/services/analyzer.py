import logging
import asyncio
from datetime import datetime, timezone
from src.core.config import config
from src.database.crud.user_service import get_active_users
from src.bot.notifier import send_liquidation_alert
from src.services.aggregator import aggregator

logger = logging.getLogger(__name__)

# Формат: { 'time': datetime, 'sum_5m': float, 'sum_1h': float }
user_alert_history = {}

async def process_liquidation_item(session, symbol: str, side_label: str, bot):
    """Принимает решение об отправке уведомления"""
    
    # 1. Мгновенно получаем всю статистику из оперативной памяти
    sum_5m, sum_1h, sum_cascade, cascade_count = aggregator.get_metrics(symbol, side_label)
    
    # 2. Получаем активных юзеров из базы
    users = await get_active_users(session)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    for user in users:
        # --- 1. ТРИГГЕРЫ (Базовые условия пробития порогов) ---
        is_cascade = (cascade_count >= config.CASCADE_TRIGGER_COUNT and 
                    sum_cascade >= user.threshold_cascade)
        
        is_vol_5m = sum_5m >= user.threshold
        is_vol_1h = sum_1h >= (user.threshold * config.VOLUME_MULTIPLIER)

        # Если ни один порог не пробит — мгновенно скипаем юзера
        if not (is_cascade or is_vol_5m or is_vol_1h):
            continue

        # --- 2. ОПРЕДЕЛЕНИЕ ТИПА (Для заголовка и фильтров юзера) ---
        # Теперь мы знаем, что событие ВАЖНОЕ. Определяем его приоритетный тип.
        if is_cascade:
            alert_type = "CASCADE"
            is_allowed = user.alert_cascade
        elif sum_5m > (sum_1h * config.SQUEEZE_RATIO):
            alert_type = "SQUEEZE"
            is_allowed = user.alert_squeeze
        else:
            alert_type = "VOLUME"
            is_allowed = user.alert_volume

        # --- 3. ФИЛЬТРАЦИЯ ПО НАСТРОЙКАМ ---
        if not is_allowed:
            continue

        # --- 4. АНТИ-СПАМ (Smart Threshold) ---
        history_key = (user.id, symbol, side_label)
        last_alert = user_alert_history.get(history_key)

        if last_alert:
            if (now - last_alert['time']).total_seconds() < config.GLOBAL_COOLDOWN_SEC:
                continue
                
            # Каскад всегда пробивает Smart Threshold, остальное — по росту объема
            if alert_type != "CASCADE":
                grew_5m = sum_5m >= last_alert['sum_5m'] * config.ALERT_GROWTH_PERCENTAGE
                grew_1h = sum_1h >= last_alert['sum_1h'] * config.ALERT_GROWTH_PERCENTAGE
                if not (grew_5m or grew_1h):
                    continue

        # --- ФОРМИРОВАНИЕ И ОТПРАВКА ---
        # Если мы дошли сюда, значит событие ВАЖНОЕ. Обновляем память.
        user_alert_history[history_key] = {
            'time': now,
            'sum_5m': sum_5m,
            'sum_1h': sum_1h
        }
        
        await send_liquidation_alert(
            bot=bot,
            user_id=user.id,
            symbol=symbol,
            side_label=side_label,
            sum_5m=sum_5m,
            sum_1h=sum_1h,
            sum_cascade=sum_cascade,
            cascade_count=cascade_count
        )

async def cleanup_alert_history_task():
    """Фоновая задача для очистки истории алертов (защита от утечки памяти)"""
    while True:
        # Проверяем раз в час
        await asyncio.sleep(3600)
        
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        threshold = now - timedelta(hours=24)
        
        # list() нужен, чтобы не было ошибки "dictionary changed size during iteration"
        keys_to_delete = [
            key for key, data in user_alert_history.items() 
            if data['time'] < threshold
        ]
        
        for key in keys_to_delete:
            del user_alert_history[key]
            
        if keys_to_delete:
            logger.info(f"Очистка памяти: удалено {len(keys_to_delete)} старых записей из истории алертов.")