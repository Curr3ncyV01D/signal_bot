import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any, TypedDict
from src.core.config import config
from src.database.crud.user_service import get_active_users
from src.database.crud.channel_service import ChannelService
from src.bot.notifier import send_liquidation_alert

logger = logging.getLogger(__name__)

USER_CACHE_TTL_SEC = 60.0


class CachedAlertTarget(TypedDict):
    id: int | str
    threshold: float
    threshold_cascade: float
    threshold_oi_percent: float
    threshold_oi_value: float
    alert_cascade: bool
    alert_oi: bool
    alert_squeeze: bool
    alert_volume: bool
    alert_rsi: bool
    alert_cvd: bool


class AlertHistoryEntry(TypedDict):
    time: datetime
    sum_5m: float


# Память алертов для анти-спама и кэш адресатов
user_alert_history: dict[tuple[int | str, str, str], AlertHistoryEntry] = {}
_cached_users: list[CachedAlertTarget] = []
_last_user_refresh: float = 0.0
_min_system_threshold: float = float("inf")
_min_system_cascade: float = float("inf")


def _build_cached_target(source: Any, target_id: int | str) -> CachedAlertTarget:
    return {
        "id": target_id,
        "threshold": float(source.threshold),
        "threshold_cascade": float(source.threshold_cascade),
        "threshold_oi_percent": float(source.threshold_oi_percent),
        "threshold_oi_value": float(source.threshold_oi_value),
        "alert_cascade": bool(source.alert_cascade),
        "alert_oi": bool(source.alert_oi),
        "alert_squeeze": bool(source.alert_squeeze),
        "alert_volume": bool(source.alert_volume),
        "alert_rsi": bool(source.alert_rsi),
        "alert_cvd": bool(source.alert_cvd),
    }


async def _refresh_user_cache(session) -> list[CachedAlertTarget]:
    global _cached_users, _last_user_refresh, _min_system_threshold, _min_system_cascade

    now_ts = datetime.now(timezone.utc).timestamp()
    if _last_user_refresh and (now_ts - _last_user_refresh) < USER_CACHE_TTL_SEC:
        return _cached_users

    cached_targets: list[CachedAlertTarget] = []
    min_threshold = float("inf")
    min_cascade = float("inf")

    for user in await get_active_users(session):
        target = _build_cached_target(user, user.id)
        cached_targets.append(target)
        min_threshold = min(min_threshold, target["threshold"])
        min_cascade = min(min_cascade, target["threshold_cascade"])

    channel_settings = ChannelService.get_cached_settings()
    if channel_settings and channel_settings.is_active:
        channel_target = _build_cached_target(channel_settings, "CHANNEL")
        cached_targets.append(channel_target)
        min_threshold = min(min_threshold, channel_target["threshold"])
        min_cascade = min(min_cascade, channel_target["threshold_cascade"])

    _cached_users = cached_targets
    _last_user_refresh = now_ts

    _min_system_threshold = (max(min_threshold, config.MIN_LIQ_VALUE_FILTER) if cached_targets else config.MIN_LIQ_VALUE_FILTER)
    _min_system_cascade = min_cascade if cached_targets else config.CASCADE_TRIGGER_COUNT * 1000
    return _cached_users

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

    # 0. Получаем быструю статистику для раннего отсечения мелких событий.
    sum_5m, sum_1h, sum_cas, count_cas = liq_aggregator.get_metrics(symbol, side_label)

    # 1. Обновляем локальный кэш адресатов максимум раз в минуту.
    targets = await _refresh_user_cache(session)
    if not targets:
        return

    # 2. Early exit: пропускаем шум рынка до любых дорогих вычислений.
    if (sum_5m < _min_system_threshold and
        (count_cas < config.CASCADE_TRIGGER_COUNT or sum_cas < _min_system_cascade)):
        return

    # 3. Тяжелые данные считаем один раз на событие.
    m_data = market_aggregator.get_market_data(symbol, window_minutes=5)
    
    _, _, delta_5m = trade_aggregator.get_cvd_metrics(symbol, minutes=5)
    _, _, delta_30m = trade_aggregator.get_cvd_metrics(symbol, minutes=30)

    rsi_val = market_aggregator.get_cached_rsi(symbol, config.RSI_PERIOD)

    # 4. Подготовка базового payload (Atomic Payload)
    # Эти данные одинаковы для всех получателей
    base_payload = {
        "symbol": symbol,
        "side_label": side_label,
        "sum_5m": sum_5m,
        "sum_1h": sum_1h,
        "sum_cascade": sum_cas,
        "cascade_count": count_cas,
        "oi_pct": m_data['oi_change_pct'] if m_data else None,
        "oi_val": m_data['oi_change_value'] if m_data else 0.0,
        "price_pct": m_data['price_change_pct'] if m_data else None,
        "total_oi": m_data['oi'] if m_data else 0.0,
        "funding": m_data['funding'] if m_data else 0.0,
        "delta_5m": delta_5m,
        "delta_30m": delta_30m,
        "rsi": rsi_val,
    }

    alert_tasks = []

    # 5. Single-pass рассылка по закэшированным адресатам.
    for target in targets:
        trigger_result = _check_triggers(
            target=target,
            symbol=symbol,
            side_label=side_label,
            sum_5m=sum_5m,
            sum_1h=sum_1h,
            sum_cas=sum_cas,
            count_cas=count_cas,
            m_data=m_data,
        )

        if trigger_result:
            recipient_id = config.PRIVATE_CHANNEL_ID if target["id"] == "CHANNEL" else int(target["id"])
            
            # Объединяем общие данные с персональными (заголовок, тип, фильтры отображения)
            full_payload = {**base_payload, **trigger_result}
            alert_tasks.append(send_liquidation_alert(bot, recipient_id, **full_payload))

    if alert_tasks:
        batch_size = 50
        for i in range(0, len(alert_tasks), batch_size):
            batch = alert_tasks[i:i + batch_size]
            await asyncio.gather(*batch, return_exceptions=True)
            await asyncio.sleep(0.01)

def _check_triggers(
    target: CachedAlertTarget,
    symbol: str,
    side_label: str,
    sum_5m: float,
    sum_1h: float,
    sum_cas: float,
    count_cas: int,
    m_data: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Универсальная логика проверки условий для пользователя или канала.
    Возвращает персональные настройки payload, если триггер сработал.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    
    # --- 1. ТРИГГЕРЫ (Базовые условия пробития порогов) ---
    is_cascade = (count_cas >= config.CASCADE_TRIGGER_COUNT and 
                sum_cas >= target["threshold_cascade"])
    
    is_vol_5m = sum_5m >= target["threshold"]
    is_vol_1h = sum_1h >= (target["threshold"] * config.VOLUME_MULTIPLIER)
    
    is_oi_pump = False
    if m_data and target["alert_oi"]:
        if m_data['oi_change_pct'] is not None and m_data['oi_change_value'] is not None:
            if (m_data['oi_change_pct'] >= target["threshold_oi_percent"] and 
                abs(m_data['oi_change_value']) >= target["threshold_oi_value"]):
                is_oi_pump = True

    # Если ни один порог не пробит — мгновенно скипаем
    if not (is_cascade or is_vol_5m or is_vol_1h or is_oi_pump):
        return None

    # --- 2. ОПРЕДЕЛЕНИЕ ТИПА (Для заголовка и фильтров) ---
    if is_cascade:
        alert_type = "CASCADE"
        alert_title = f"⚡️ LIQ КАСКАД x{count_cas}"
        is_allowed = target["alert_cascade"]
    elif is_oi_pump:
        alert_type = "OI_PUMP"
        alert_title = "📈 OI PUMP"
        is_allowed = target["alert_oi"]
    elif sum_5m > (sum_1h * config.SQUEEZE_RATIO):
        alert_type = "SQUEEZE"
        alert_title = "🔥 QUICK SQUEEZE"
        is_allowed = target["alert_squeeze"]
    else:
        alert_type = "VOLUME"
        alert_title = "📊 LIQ VOLUME"
        is_allowed = target["alert_volume"]

    # --- 3. ФИЛЬТРАЦИЯ ПО НАСТРОЙКАМ ---
    if not is_allowed:
        return None

    # --- 4. АНТИ-СПАМ (Smart Threshold) ---
    target_id = target["id"]
    history_key = (target_id, symbol, side_label)
    last_alert = user_alert_history.get(history_key)

    if last_alert:
        if (now - last_alert['time']).total_seconds() < config.GLOBAL_COOLDOWN_SEC:
            return None
            
        if alert_type not in ["CASCADE", "OI_PUMP"]:
            grew_5m = sum_5m >= last_alert['sum_5m'] * config.ALERT_GROWTH_PERCENTAGE
            if not grew_5m:
                return None

    # --- 5. ФОРМИРОВАНИЕ ПЕРСОНАЛЬНОГО ПЕЙЛОАДА ---
    user_alert_history[history_key] = {
        'time': now,
        'sum_5m': sum_5m
    }
    
    return {
        "alert_title": alert_title,
        "alert_type": alert_type,
        "threshold_cascade": target["threshold_cascade"],
        "show_oi": target["alert_oi"],
        "show_cvd": target["alert_cvd"],
        "show_rsi": target["alert_rsi"]
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
