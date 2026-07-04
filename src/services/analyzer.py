import asyncio
import logging
from time import time
from typing import Any, TypedDict, cast
from uuid import uuid4

from src.core.config import config
from src.core.dto import SignalAlertType, SignalDTO, SignalOhlcRow, SignalSideLabel
from src.core.redis_bus import redis_bus
from src.database.crud.channel_service import ChannelService
from src.database.crud.user_service import get_active_users
from src.database.session import async_session

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


class GlobalSignalHistoryEntry(TypedDict):
    time: float
    sum_5m: float


_cached_users: list[CachedAlertTarget] = []
_min_system_threshold: float = float("inf")
_min_system_cascade: float = float("inf")
global_signal_history: dict[tuple[str, str], GlobalSignalHistoryEntry] = {}


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
        "alert_cvd": bool(source.alert_cvd),
    }


async def _update_cache_logic() -> None:
    global _cached_users, _min_system_threshold, _min_system_cascade

    async with async_session() as session:
        cached_targets: list[CachedAlertTarget] = []
        min_threshold = float("inf")
        min_cascade = float("inf")

        active_users = await get_active_users(session, force_refresh=True)
        for user in active_users:
            target = _build_cached_target(user, user.id)
            cached_targets.append(target)
            min_threshold = min(min_threshold, target["threshold"])
            min_cascade = min(min_cascade, target["threshold_cascade"])

        channel_settings = await ChannelService.get_settings(session)
        if channel_settings and channel_settings.is_active:
            channel_target = _build_cached_target(channel_settings, "CHANNEL")
            cached_targets.append(channel_target)
            min_threshold = min(min_threshold, channel_target["threshold"])
            min_cascade = min(min_cascade, channel_target["threshold_cascade"])

        _cached_users = cached_targets
        _min_system_threshold = (
            max(min_threshold, config.MIN_LIQ_VALUE_FILTER)
            if cached_targets
            else config.MIN_LIQ_VALUE_FILTER
        )
        _min_system_cascade = (
            min_cascade
            if cached_targets
            else config.CASCADE_TRIGGER_COUNT * 1000
        )


async def user_cache_refresher_task() -> None:
    while True:
        try:
            await _update_cache_logic()
        except Exception as exc:
            logger.error(f"Ошибка в задаче обновления кэша пользователей: {exc}")
        await asyncio.sleep(60)


async def invalidate_user_cache(user_id: int | None = None) -> None:
    try:
        await _update_cache_logic()
        invalidation_payload = str(user_id) if user_id is not None else "ALL"
        await redis_bus.publish_cache_invalidation(invalidation_payload)
        logger.info("♻️ Кэш пользователей принудительно обновлен.")
    except Exception as exc:
        logger.error(f"Ошибка при инвалидации кэша пользователей: {exc}")


async def user_cache_refresher_task_once() -> None:
    try:
        await _update_cache_logic()
        logger.info("✅ Первоначальный кэш пользователей успешно загружен.")
    except Exception as exc:
        logger.error(f"❌ Критическая ошибка при начальной загрузке кэша: {exc}")


def _resolve_stream_signal_metadata(
    *,
    sum_5m: float,
    sum_1h: float,
    sum_cascade: float,
    cascade_count: int,
    m_data: dict[str, Any] | None,
) -> tuple[SignalAlertType, str]:
    has_cascade = (
        cascade_count >= config.CASCADE_TRIGGER_COUNT
        and sum_cascade >= _min_system_cascade
    )

    oi_pct = m_data.get("oi_change_pct") if m_data else None
    oi_val = m_data.get("oi_change_value") if m_data else None
    has_oi_pump = (
        oi_pct is not None
        and oi_val is not None
        and oi_pct >= 0
        and oi_pct >= config.MIN_OI_CHANGE_PCT
        and abs(oi_val) >= config.MIN_LIQ_VALUE_FILTER
    )

    has_volume = (
        sum_5m >= _min_system_threshold
        or sum_1h >= (_min_system_threshold * config.VOLUME_MULTIPLIER)
    )
    has_squeeze = has_volume and sum_5m > (sum_1h * config.SQUEEZE_RATIO)

    if has_cascade:
        return "CASCADE", f"⚡️ LIQ КАСКАД x{cascade_count}"
    if has_oi_pump:
        return "OI_PUMP", "📈 OI PUMP"
    if has_squeeze:
        return "SQUEEZE", "🔥 QUICK SQUEEZE"
    return "VOLUME", "📊 LIQ VOLUME"


def _serialize_ohlc_history(ohlc_data: list[dict[str, int | float]]) -> list[SignalOhlcRow]:
    compact_rows: list[SignalOhlcRow] = []
    for candle in ohlc_data[-100:]:
        compact_rows.append(
            [
                int(candle["t"]),
                float(candle["o"]),
                float(candle["h"]),
                float(candle["l"]),
                float(candle["c"]),
                float(candle["v"]),
            ]
        )
    return compact_rows


def _build_raw_signal_dto(
    *,
    signal_id: str,
    symbol: str,
    side_label: str,
    sum_5m: float,
    sum_1h: float,
    sum_cascade: float,
    cascade_count: int,
    m_data: dict[str, Any] | None,
    impact: dict[str, Any],
    delta_5m: float | None,
    delta_30m: float | None,
    rsi_val: float | None,
    ohlc_history: list[SignalOhlcRow],
    timestamp: float,
) -> SignalDTO:
    alert_type, alert_title = _resolve_stream_signal_metadata(
        sum_5m=sum_5m,
        sum_1h=sum_1h,
        sum_cascade=sum_cascade,
        cascade_count=cascade_count,
        m_data=m_data,
    )

    return {
        "signal_id": signal_id,
        "symbol": symbol,
        "side_label": cast(SignalSideLabel, side_label),
        "alert_type": alert_type,
        "alert_title": alert_title,
        "market_data": {
            "sum_5m": sum_5m,
            "sum_1h": sum_1h,
            "sum_cascade": sum_cascade,
            "cascade_count": cascade_count,
            "oi_pct": m_data["oi_change_pct"] if m_data else None,
            "oi_val": m_data["oi_change_value"] if m_data else 0.0,
            "price_pct": m_data["price_change_pct"] if m_data else None,
            "total_oi": m_data["oi"] if m_data else 0.0,
            "funding": m_data["funding"] if m_data else 0.0,
            "rsi": rsi_val,
        },
        "impact_metrics": {
            "cap_ratio": impact["cap_ratio"],
            "vol_ratio": impact["vol_ratio"],
            "live_mcap": impact["live_mcap"],
            "is_fallback": impact["is_fallback"],
        },
        "trade_metrics": {
            "delta_5m": delta_5m,
            "delta_30m": delta_30m,
        },
        "settings": {
            "show_oi": True,
            "show_cvd": True,
            "show_rsi": True,
            "used_mcap": False,
        },
        "ohlc_history": ohlc_history,
        "chart_file_id": None,
        "timestamp": timestamp,
    }


async def process_liquidation_item(
    symbol: str,
    side_label: str,
    liq_aggregator,
    market_aggregator,
    trade_aggregator,
) -> None:
    sum_5m, sum_1h, sum_cascade, cascade_count = liq_aggregator.get_metrics(symbol, side_label)

    if not _cached_users:
        return

    if (
        sum_5m < _min_system_threshold
        and (cascade_count < config.CASCADE_TRIGGER_COUNT or sum_cascade < _min_system_cascade)
    ):
        return

    history_key = (symbol, side_label)
    last_entry = global_signal_history.get(history_key)
    current_time = time()
    if last_entry is not None:
        cooldown_elapsed = (current_time - last_entry["time"]) >= config.GLOBAL_COOLDOWN_SEC
        grew_enough = sum_5m >= (last_entry["sum_5m"] * config.ALERT_GROWTH_PERCENTAGE)
        if not cooldown_elapsed and not grew_enough:
            return

    global_signal_history[history_key] = {
        "time": current_time,
        "sum_5m": sum_5m,
    }

    m_data = market_aggregator.get_market_data(symbol, window_minutes=5)
    _, _, delta_5m = trade_aggregator.get_cvd_metrics(symbol, minutes=5)
    _, _, delta_30m = trade_aggregator.get_cvd_metrics(symbol, minutes=30)
    rsi_val = market_aggregator.get_cached_rsi(symbol, config.RSI_PERIOD)
    impact = market_aggregator.get_impact_metrics(symbol, sum_5m)
    ohlc_history = _serialize_ohlc_history(list(market_aggregator.ohlc_history.get(symbol, [])))

    dto = _build_raw_signal_dto(
        signal_id=str(uuid4()),
        symbol=symbol,
        side_label=side_label,
        sum_5m=sum_5m,
        sum_1h=sum_1h,
        sum_cascade=sum_cascade,
        cascade_count=cascade_count,
        m_data=m_data,
        impact=impact,
        delta_5m=delta_5m,
        delta_30m=delta_30m,
        rsi_val=rsi_val,
        ohlc_history=ohlc_history,
        timestamp=current_time,
    )

    try:
        await redis_bus.publish_signal_to_stream(dto, config.REDIS_RAW_STREAM_NAME)
    except Exception as exc:
        logger.error(f"Ошибка публикации в Redis: {exc}")


async def cleanup_alert_history_task() -> None:
    while True:
        await asyncio.sleep(3600)
        now = time()
        threshold = now - (24 * 3600)

        expired_keys = [
            key
            for key in list(global_signal_history.keys())
            if global_signal_history[key]["time"] < threshold
        ]

        for key in expired_keys:
            global_signal_history.pop(key, None)

        if expired_keys:
            logger.debug(f"🧹 Очистка истории Brain: удалено {len(expired_keys)} устаревших записей.")
