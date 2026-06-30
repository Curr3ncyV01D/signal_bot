import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any, TypedDict
from src.core.config import config
from src.database.session import async_session
from src.database.crud.user_service import get_active_users
from src.database.crud.channel_service import ChannelService
from src.bot.notifier import send_liquidation_alert
from src.services import chart_generator
from src.utils import strip_emojis

logger = logging.getLogger(__name__)


class CachedAlertTarget(TypedDict):
    id: int | str
    threshold: float
    threshold_cascade: float
    threshold_mode: str
    threshold_mcap_pct: float
    threshold_mcap_usd_min: float
    threshold_cascade_mcap_pct: float
    threshold_cascade_mcap_usd_min: float
    threshold_oi_percent: float
    threshold_oi_value: float
    alert_cascade: bool
    alert_oi: bool
    alert_squeeze: bool
    alert_volume: bool
    alert_longs: bool
    alert_shorts: bool
    alert_rsi: bool
    alert_cvd: bool

class AlertHistoryEntry(TypedDict):
    time: datetime
    sum_5m: float


# Память алертов для анти-спама и кэш адресатов
user_alert_history: dict[tuple[int | str, str, str], AlertHistoryEntry] = {}
_cached_users: list[CachedAlertTarget] = []
_min_system_threshold: float = float("inf")
_min_system_cascade: float = float("inf")


def _build_cached_target(source: Any, target_id: int | str) -> CachedAlertTarget:
    return {
        "id": target_id,
        "threshold": float(source.threshold),
        "threshold_cascade": float(source.threshold_cascade),
        "threshold_mode": str(source.threshold_mode),
        "threshold_mcap_pct": float(source.threshold_mcap_pct),
        "threshold_mcap_usd_min": float(source.threshold_mcap_usd_min),
        "threshold_cascade_mcap_pct": float(source.threshold_cascade_mcap_pct),
        "threshold_cascade_mcap_usd_min": float(source.threshold_cascade_mcap_usd_min),
        "threshold_oi_percent": float(source.threshold_oi_percent),
        "threshold_oi_value": float(source.threshold_oi_value),
        "alert_cascade": bool(source.alert_cascade),
        "alert_oi": bool(source.alert_oi),
        "alert_squeeze": bool(source.alert_squeeze),
        "alert_volume": bool(source.alert_volume),
        "alert_longs": bool(source.alert_longs),
        "alert_shorts": bool(source.alert_shorts),
        "alert_rsi": bool(source.alert_rsi),
        "alert_cvd": bool(source.alert_cvd)
    }


async def _update_cache_logic():
    """Внутренняя логика обновления кэша."""
    global _cached_users, _min_system_threshold, _min_system_cascade
    async with async_session() as session:
        cached_targets: list[CachedAlertTarget] = []
        min_threshold = float("inf")
        min_cascade = float("inf")

        # 1. Получаем активных пользователей
        active_users = await get_active_users(session)
        for user in active_users:
            target = _build_cached_target(user, user.id)
            cached_targets.append(target)
            min_threshold = min(min_threshold, target["threshold"])
            min_cascade = min(min_cascade, target["threshold_cascade"])

        # 2. Получаем настройки канала
        channel_settings = await ChannelService.get_settings(session)
        if channel_settings and channel_settings.is_active:
            channel_target = _build_cached_target(channel_settings, "CHANNEL")
            cached_targets.append(channel_target)
            min_threshold = min(min_threshold, channel_target["threshold"])
            min_cascade = min(min_cascade, channel_target["threshold_cascade"])

        # 3. Атомарно обновляем глобальные переменные
        _cached_users = cached_targets
        _min_system_threshold = (max(min_threshold, config.MIN_LIQ_VALUE_FILTER) 
                                if cached_targets else config.MIN_LIQ_VALUE_FILTER)
        _min_system_cascade = min_cascade if cached_targets else config.CASCADE_TRIGGER_COUNT * 1000

async def user_cache_refresher_task():
    """Фоновая задача для обновления кэша пользователей и настроек канала."""
    while True:
        try:
            await _update_cache_logic()
        except Exception as e:
            logger.error(f"Ошибка в задаче обновления кэша пользователей: {e}")
        await asyncio.sleep(60)

async def invalidate_user_cache():
    """Принудительное обновление кэша пользователей (например, после покупки подписки)."""
    try:
        await _update_cache_logic()
        logger.info("♻️ Кэш пользователей принудительно обновлен.")
    except Exception as e:
        logger.error(f"Ошибка при инвалидации кэша пользователей: {e}")

async def user_cache_refresher_task_once():
    """Однократное обновление кэша для Graceful Startup."""
    try:
        await _update_cache_logic()
        logger.info("✅ Первоначальный кэш пользователей успешно загружен.")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при начальной загрузке кэша: {e}")
        # Не прокидываем ошибку дальше, чтобы не убить старт, 
        # но система будет ждать следующего цикла обновления.

async def process_liquidation_item(
    symbol: str, 
    side_label: str, 
    bot, 
    liq_aggregator, 
    market_aggregator, 
    trade_aggregator
):
    """Принимает решение об отправке уведомления и выполняет рассылку через gather.
    Полностью In-Memory обработка.
    """

    # 0. Получаем быструю статистику для раннего отсечения мелких событий.
    sum_5m, sum_1h, sum_cas, count_cas = liq_aggregator.get_metrics(symbol, side_label)

    # 1. Используем закэшированных адресатов.
    targets = _cached_users
    if not targets:
        return

    # 2. Early exit: пропускаем шум рынка до любых дорогих вычислений.
    if (sum_5m < _min_system_threshold and
        (count_cas < config.CASCADE_TRIGGER_COUNT or sum_cas < _min_system_cascade)):
        return

    # 3. Получение дополнительных данных из агрегаторов
    m_data = market_aggregator.get_market_data(symbol, window_minutes=5)
    _, _, delta_5m = trade_aggregator.get_cvd_metrics(symbol, minutes=5)
    _, _, delta_30m = trade_aggregator.get_cvd_metrics(symbol, minutes=30)
    rsi_val = market_aggregator.get_cached_rsi(symbol, config.RSI_PERIOD)

    # 3.1 Расчет метрик влияния на рынок (Cap Ratio, Vol Ratio)
    impact = market_aggregator.get_impact_metrics(symbol, sum_5m)
    impact_1h = market_aggregator.get_impact_metrics(symbol, sum_1h)
    impact_cas = market_aggregator.get_impact_metrics(symbol, sum_cas)

    if impact["is_fallback"]:
        pass

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
        "vol_ratio": impact["vol_ratio"],
        "live_mcap": impact["live_mcap"],
        "cap_ratio": impact["cap_ratio"],
        "is_fallback": impact["is_fallback"],
    }

    ohlc_data = list(market_aggregator.ohlc_history.get(symbol, []))
    prepared_alerts: list[tuple[int | str, dict[str, Any]]] = []

    # 5. Single-pass рассылка по закэшированным адресатам.
    for target in targets:
        try:
            trigger_result = _check_triggers(
                target=target,
                symbol=symbol,
                side_label=side_label,
                sum_5m=sum_5m,
                sum_1h=sum_1h,
                sum_cas=sum_cas,
                count_cas=count_cas,
                m_data=m_data,
                impact=impact,
                impact_1h=impact_1h,
                impact_cas=impact_cas
            )
        except Exception as e:
            logger.error(f"Ошибка проверки триггеров для {target['id']}: {e}")
            continue

        if trigger_result:
            recipient_id = config.PRIVATE_CHANNEL_ID if target["id"] == "CHANNEL" else int(target["id"])
            # Объединяем общие данные с персональными (заголовок, тип, фильтры отображения)
            full_payload = {**base_payload, **trigger_result}
            prepared_alerts.append((recipient_id, full_payload))

    if not prepared_alerts:
        return

    async def _dispatch_batches(alert_tasks: list[Any]) -> None:
        batch_size = 50
        for i in range(0, len(alert_tasks), batch_size):
            batch = alert_tasks[i:i + batch_size]
            await asyncio.gather(*batch, return_exceptions=True)
            await asyncio.sleep(0.01)

    current_price = float(impact["price"])

    # 6. Fallback на текст, если график еще не готов или цена некорректна.
    if len(ohlc_data) < 30 or current_price <= 0:
        await _dispatch_batches([
            send_liquidation_alert(bot, recipient_id, **payload)
            for recipient_id, payload in prepared_alerts
        ])
        return

    # 7. Сценарий cache-hit: мгновенная массовая рассылка по file_id.
    cached_id = chart_generator.get_cached_id(symbol, current_price)
    if cached_id:
        await _dispatch_batches([
            send_liquidation_alert(bot, recipient_id, photo_file_id=cached_id, **payload)
            for recipient_id, payload in prepared_alerts
        ])
        return

    # 8. Cache-miss: один рендер на символ под локом + harvesting первого успешного file_id.
    async with chart_generator.locks[symbol]:
        cached_id = chart_generator.get_cached_id(symbol, current_price)
        if cached_id:
            await _dispatch_batches([
                send_liquidation_alert(bot, recipient_id, photo_file_id=cached_id, **payload)
                for recipient_id, payload in prepared_alerts
            ])
            return

        alert_title = str(prepared_alerts[0][1].get("alert_title", "LIQUIDATION ALERT"))
        chart_title = strip_emojis(alert_title)

        chart_bytes = await chart_generator.get_chart(symbol, ohlc_data, chart_title)
        if chart_bytes is None:
            await _dispatch_batches([
                send_liquidation_alert(bot, recipient_id, **payload)
                for recipient_id, payload in prepared_alerts
            ])
            return

        remaining_alerts = prepared_alerts.copy()
        harvested_file_id: str | None = None

        while remaining_alerts and harvested_file_id is None:
            first_recipient, first_payload = remaining_alerts.pop(0)
            harvested_file_id = await send_liquidation_alert(
                bot,
                first_recipient,
                photo_bytes=chart_bytes,
                **first_payload,
            )

        if harvested_file_id:
            chart_generator.update_cache(symbol, harvested_file_id, current_price)
            if remaining_alerts:
                await _dispatch_batches([
                    send_liquidation_alert(bot, recipient_id, photo_file_id=harvested_file_id, **payload)
                    for recipient_id, payload in remaining_alerts
                ])
            return

        # Если harvesting не удался ни у одного получателя, дополнительных повторов не делаем.
        return

def _check_triggers(
    target: CachedAlertTarget,
    symbol: str,
    side_label: str,
    sum_5m: float,
    sum_1h: float,
    sum_cas: float,
    count_cas: int,
    m_data: dict[str, Any] | None,
    impact: dict[str, Any],
    impact_1h: dict[str, Any],
    impact_cas: dict[str, Any]
) -> dict[str, Any] | None:
    """Универсальная логика проверки условий для пользователя или канала.
    Возвращает персональные настройки payload, если триггер сработал.
    """
    # --- 0. ФИЛЬТРАЦИЯ НАПРАВЛЕНИЯ (Early Return) ---
    if side_label == "LONG" and not target.get("alert_longs", True):
        return None
    if side_label == "SHORT" and not target.get("alert_shorts", True):
        return None

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    
    # --- 1. ОПРЕДЕЛЕНИЕ РЕЖИМА (Smart Fallback) ---
    effective_mode = "USD" if impact["is_fallback"] else target["threshold_mode"]
    used_mcap = (effective_mode == "PERCENT")

    # --- 2. ТРИГГЕРЫ (Определяем все возможные события) ---
    if effective_mode == "PERCENT":
        # Логика по капитализации (Cap Ratio)
        cap_ratio_5m = impact["cap_ratio"] or 0.0
        cap_ratio_1h = impact_1h["cap_ratio"] or 0.0
        cap_ratio_cas = impact_cas["cap_ratio"] or 0.0

        has_cascade = (count_cas >= config.CASCADE_TRIGGER_COUNT and 
                     cap_ratio_cas >= target["threshold_cascade_mcap_pct"] and
                     sum_cas >= target["threshold_cascade_mcap_usd_min"])
        
        has_volume = (cap_ratio_5m >= target["threshold_mcap_pct"] and 
                    sum_5m >= target["threshold_mcap_usd_min"]) or \
                   (cap_ratio_1h >= (target["threshold_mcap_pct"] * config.VOLUME_MULTIPLIER) and 
                    sum_1h >= (target["threshold_mcap_usd_min"] * config.VOLUME_MULTIPLIER))
    else:
        # Логика по USD (Классическая)
        has_cascade = (count_cas >= config.CASCADE_TRIGGER_COUNT and 
                     sum_cas >= target["threshold_cascade"])
        
        has_volume = (sum_5m >= target["threshold"] or 
                    sum_1h >= (target["threshold"] * config.VOLUME_MULTIPLIER))
    
    has_oi_pump = False
    if m_data:
        oi_pct = m_data.get('oi_change_pct')
        oi_val = m_data.get('oi_change_value')
        if oi_pct is not None and oi_val is not None:
            if (oi_pct >= target["threshold_oi_percent"] and 
                abs(oi_val) >= target["threshold_oi_value"]):
                has_oi_pump = True

    has_squeeze = has_volume and sum_5m > (sum_1h * config.SQUEEZE_RATIO)

    # --- 3. ВЫБОР ТИПА ПО ПРИОРИТЕТУ И НАСТРОЙКАМ ПОЛЬЗОВАТЕЛЯ ---
    alert_type = None
    alert_title = ""

    if has_cascade and target["alert_cascade"]:
        alert_type = "CASCADE"
        alert_title = f"⚡️ LIQ КАСКАД x{count_cas}"
    elif has_oi_pump and target["alert_oi"]:
        alert_type = "OI_PUMP"
        alert_title = "📈 OI PUMP"
    elif has_squeeze and target["alert_squeeze"]:
        alert_type = "SQUEEZE"
        alert_title = "🔥 QUICK SQUEEZE"
    elif has_volume and target["alert_volume"]:
        alert_type = "VOLUME"
        alert_title = "📊 LIQ VOLUME"
    
    # Если ни один из сработавших триггеров не разрешен пользователем
    if not alert_type:
        return None

    # --- 4. АНТИ-СПАМ (Smart Threshold) ---
    target_id = target["id"]
    history_key = (target_id, symbol, side_label)
    last_alert = user_alert_history.get(history_key)

    if last_alert:
        # Проверка кулдауна (общая для всех типов)
        if (now - last_alert['time']).total_seconds() < config.GLOBAL_COOLDOWN_SEC:
            return None
            
        # Проверка прироста (только для VOLUME и SQUEEZE)
        if alert_type in ["VOLUME", "SQUEEZE"]:
            grew_enough = sum_5m >= last_alert['sum_5m'] * config.ALERT_GROWTH_PERCENTAGE
            if not grew_enough:
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
        "show_rsi": target["alert_rsi"],
        "used_mcap": used_mcap
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
