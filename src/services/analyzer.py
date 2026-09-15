import asyncio
import logging
from time import time
from typing import Any, TypedDict, cast
from uuid import uuid4

import orjson

from src.core.config import config
from src.core.dto import SignalAlertType, SignalDTO, SignalOhlcRow, SignalSideLabel
from src.core.localization import normalize_locale_code
from src.core.redis_bus import redis_bus
from src.database.crud.user_service import get_active_users
from src.database.functions import get_utc_now
from src.database.session import async_session
from src.services.logic.trigger_engine import (
    build_alert_title,
    evaluate_trigger_logic,
    is_signal_spammy,
)

logger = logging.getLogger(__name__)


class CachedAlertTarget(TypedDict):
    id: int
    language_code: str
    is_vip: bool
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
    filter_rsi_min: float
    filter_rsi_max: float


class GlobalSignalHistoryEntry(TypedDict):
    time: float
    sum_5m: float


_cached_users: list[CachedAlertTarget] = []
_min_system_threshold: float = float("inf")
_min_system_cascade: float = float("inf")


def _brain_history_redis_key(symbol: str, side_label: str) -> str:
    return f"csl:brain:history:{symbol}:{side_label}"


def _decode_redis_payload(payload: bytes | str | None) -> bytes | None:
    if payload is None:
        return None
    if isinstance(payload, bytes):
        return payload
    return payload.encode("utf-8")


def _build_cached_target(source: Any, target_id: int) -> CachedAlertTarget:
    subscription_end = getattr(source, "subscription_end", None)
    is_blocked = bool(getattr(source, "is_blocked", False))
    is_vip = bool(
        subscription_end is not None
        and subscription_end > get_utc_now()
        and not is_blocked
    )
    return {
        "id": target_id,
        "language_code": normalize_locale_code(getattr(source, "language_code", None)),
        "is_vip": is_vip,
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
        "filter_rsi_min": float(getattr(source, "filter_rsi_min", 100.0)),
        "filter_rsi_max": float(getattr(source, "filter_rsi_max", 0.0)),
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

        _cached_users = cached_targets
        _min_system_threshold = (
            max(min_threshold, config.MIN_LIQ_VALUE_FILTER)
            if cached_targets
            else float("inf")
        )
        _min_system_cascade = (
            min_cascade
            if cached_targets
            else float("inf")
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


def _should_render_chart(
    *,
    alert_type: SignalAlertType,
    sum_5m: float,
    sum_1h: float,
    impact: dict[str, Any],
    rsi_val: float | None,
) -> bool:
    if alert_type in config.CHART_ALWAYS_RENDER_TYPES:
        return True
    if sum_5m >= config.CHART_MIN_VOLUME_USD:
        return True
    if sum_1h >= config.CHART_MIN_VOLUME_USD * config.VOLUME_MULTIPLIER:
        return True

    vol_ratio = impact.get("vol_ratio")
    if vol_ratio is not None and vol_ratio >= config.CHART_MIN_VOL_RATIO:
        return True

    if (
        rsi_val is not None
        and sum_5m > 2000.0
        and (
            rsi_val >= config.CHART_RSI_EXTREME_UPPER
            or rsi_val <= config.CHART_RSI_EXTREME_LOWER
        )
    ):
        return True

    cap_ratio = impact.get("cap_ratio")
    return cap_ratio is not None and cap_ratio >= config.CHART_MIN_CAP_RATIO


def _build_raw_signal_dto(
    *,
    signal_id: str,
    symbol: str,
    side_label: str,
    alert_type: SignalAlertType,
    alert_title: str,
    render_requested: bool,
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
    return {
        "signal_id": signal_id,
        "symbol": symbol,
        "side_label": cast(SignalSideLabel, side_label),
        "alert_type": alert_type,
        "alert_title": alert_title,
        "render_requested": render_requested,
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
        "chart_message_id": None,
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

    m_data = market_aggregator.get_market_data(symbol, window_minutes=5)
    rsi_val = market_aggregator.get_cached_rsi(symbol, config.RSI_PERIOD)
    alert_type = evaluate_trigger_logic(
        sum_5m=sum_5m,
        sum_1h=sum_1h,
        sum_cascade=sum_cascade,
        cascade_count=cascade_count,
        oi_pct=m_data.get("oi_change_pct") if m_data else None,
        oi_val=m_data.get("oi_change_value") if m_data else None,
        volume_threshold=_min_system_threshold,
        cascade_threshold=_min_system_cascade,
        oi_threshold_pct=config.MIN_OI_CHANGE_PCT,
        oi_threshold_value=config.MIN_LIQ_VALUE_FILTER,
        cascade_trigger_count=config.CASCADE_TRIGGER_COUNT,
        volume_multiplier=config.VOLUME_MULTIPLIER,
        squeeze_ratio=config.SQUEEZE_RATIO,
        require_nonnegative_oi_pct=True,
        current_rsi=rsi_val,
        rsi_min=100.0,
        rsi_max=0.0,
    )
    if alert_type is None:
        return
    alert_title = build_alert_title(alert_type, cascade_count)
    current_time = time()
    history_key = _brain_history_redis_key(symbol, side_label)
    raw_last_entry = _decode_redis_payload(await redis_bus.get_key(history_key))
    if raw_last_entry is not None:
        try:
            last_entry = cast(GlobalSignalHistoryEntry, orjson.loads(raw_last_entry))
        except Exception:
            last_entry = None
        if last_entry is not None and is_signal_spammy(
            last_time=float(last_entry.get("time", 0.0)),
            current_time=current_time,
            last_sum=float(last_entry.get("sum_5m", 0.0)),
            current_sum=sum_5m,
            cooldown_limit=float(config.GLOBAL_COOLDOWN_SEC),
            growth_multiplier=float(config.ALERT_GROWTH_PERCENTAGE),
        ):
            return

    _, _, delta_5m = trade_aggregator.get_cvd_metrics(symbol, minutes=5)
    _, _, delta_30m = trade_aggregator.get_cvd_metrics(symbol, minutes=30)
    impact = market_aggregator.get_impact_metrics(symbol, sum_5m)
    render_requested = _should_render_chart(
        alert_type=alert_type,
        sum_5m=sum_5m,
        sum_1h=sum_1h,
        impact=impact,
        rsi_val=rsi_val,
    )
    ohlc_history = (
        _serialize_ohlc_history(list(market_aggregator.ohlc_history.get(symbol, [])))
        if render_requested
        else []
    )

    dto = _build_raw_signal_dto(
        signal_id=str(uuid4()),
        symbol=symbol,
        side_label=side_label,
        alert_type=alert_type,
        alert_title=alert_title,
        render_requested=render_requested,
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

    message_id = await redis_bus.publish_signal_to_stream(dto, config.REDIS_RAW_STREAM_NAME)
    if message_id is None:
        logger.error("Ошибка публикации в Redis: signal не был записан в stream.")
        return

    await redis_bus.set_key(
        history_key,
        orjson.dumps({"time": current_time, "sum_5m": sum_5m}).decode("utf-8"),
        expire_seconds=3600,
    )
