import logging
from datetime import datetime, timezone
from src.core.config import config
from src.database.crud import get_active_users
from src.bot.notifier import send_liquidation_alert
from src.services.aggregator import aggregator
from src.services.statistics import stats_manager

logger = logging.getLogger(__name__)

# Формат: { 'time': datetime, 'sum_5m': float, 'sum_1h': float }
user_alert_history = {}

async def process_liquidation_item(session, symbol: str, side_label: str, bot):
    """Принимает решение об отправке уведомления"""
    
    # 1. Мгновенно получаем всю статистику из оперативной памяти
    sum_5m, sum_1h, cascade_count = aggregator.get_metrics(symbol, side_label)
    
    # 2. Получаем активных юзеров из базы
    users = await get_active_users(session)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    for user in users:

        # --- ОПРЕДЕЛЕНИЕ ТИПА УВЕДОМЛЕНИЯ ---
        # Логика приоритетов: каскад > сквиз > объем
        is_cascade_now = cascade_count >= config.CASCADE_TRIGGER_COUNT
        is_squeeze_now = sum_5m > (sum_1h * config.SQUEEZE_RATIO)
        is_volume_now = sum_1h >= (user.threshold * config.VOLUME_MULTIPLIER) or sum_5m >= user.threshold

        # --- ФИЛЬТРАЦИЯ ПО НАСТРОЙКАМ УВЕДОМЛЕНИЙ ---
        if is_cascade_now and not user.alert_cascade:
            continue
        if is_squeeze_now and not is_cascade_now and not user.alert_squeeze:
            continue
        if is_volume_now and not is_cascade_now and not is_squeeze_now and not user.alert_volume:
            continue


        # --- ПРОВЕРКА ТРИГГЕРОВ ---
        # Проверяем, выполнено ли ХОТЯ БЫ ОДНО условие для тревоги
        is_5m_triggered = sum_5m >= user.threshold
        is_1h_triggered = sum_1h >= (user.threshold * config.VOLUME_MULTIPLIER)
        is_cascade = cascade_count >= config.CASCADE_TRIGGER_COUNT
        
        if not (is_5m_triggered or is_1h_triggered or is_cascade):
            continue # Рынок спокоен, пороги не пробиты

        # --- АНТИ-СПАМ (Smart Threshold) ---
        history_key = (user.id, symbol, side_label) 
        last_alert = user_alert_history.get(history_key)

        if last_alert:
            # Жесткий кулдаун: минимум сколько-то секунд между любыми сообщениями по одной монете
            if (now - last_alert['time']).total_seconds() < config.GLOBAL_COOLDOWN_SEC:
                continue
                
            # Проверка "Значимости" прироста
            # Если это не новый каскад, то сумма должна вырасти минимум на заданный процент от прошлого алерта
            grew_5m = sum_5m >= last_alert['sum_5m'] * config.ALERT_GROWTH_PERCENTAGE
            grew_1h = sum_1h >= last_alert['sum_1h'] * config.ALERT_GROWTH_PERCENTAGE
            
            # Если суммы не выросли и это не каскад - пропускаем
            if not (grew_5m or grew_1h or is_cascade):
                continue

        # --- ФОРМИРОВАНИЕ И ОТПРАВКА ---
        # Если мы дошли сюда, значит событие ВАЖНОЕ. Обновляем память.
        user_alert_history[history_key] = {
            'time': now,
            'sum_5m': sum_5m,
            'sum_1h': sum_1h
        }

        # Статистика отправки сигналов за 24 часа
        stats_manager.add_signal(user.id)
        user_signals_24h = stats_manager.get_count_24h(user.id)
        
        await send_liquidation_alert(
            bot=bot,
            user_id=user.id,
            symbol=symbol,
            side_label=side_label,
            sum_5m=sum_5m,
            sum_1h=sum_1h,
            cascade_count=cascade_count,
            signals_24h=user_signals_24h
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