import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, TypedDict

from aiogram import Bot

from src.bot.notifier import build_alert_payload, send_liquidation_alert
from src.core.config import config, setup_logging
from src.core.dto import SignalAlertType, SignalDTO
from src.core.redis_bus import redis_bus
from src.database.crud.channel_service import ChannelService
from src.database.crud.user_service import get_active_users, get_user_by_id
from src.database.functions import get_utc_now
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


class AlertHistoryEntry(TypedDict):
    time: datetime
    sum_5m: float


class TriggerResult(TypedDict):
    alert_title: str
    alert_type: SignalAlertType
    threshold_cascade: float
    show_oi: bool
    show_cvd: bool
    show_rsi: bool
    used_mcap: bool


user_alert_history: dict[tuple[int | str, str, str], AlertHistoryEntry] = {}


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


def _is_user_active(user: Any) -> bool:
    subscription_end = getattr(user, "subscription_end", None)
    return (
        user is not None
        and not bool(getattr(user, "is_blocked", False))
        and subscription_end is not None
        and subscription_end > get_utc_now()
    )


def _check_triggers_from_dto(
    target: CachedAlertTarget,
    dto: SignalDTO,
) -> TriggerResult | None:
    side_label = dto["side_label"]
    if side_label == "LONG" and not target.get("alert_longs", True):
        return None
    if side_label == "SHORT" and not target.get("alert_shorts", True):
        return None

    market_data = dto["market_data"]
    impact = dto["impact_metrics"]

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    effective_mode = "USD" if impact["is_fallback"] else target["threshold_mode"]
    used_mcap = effective_mode == "PERCENT"

    sum_5m = market_data["sum_5m"]
    sum_1h = market_data["sum_1h"]
    sum_cascade = market_data["sum_cascade"]
    cascade_count = market_data["cascade_count"]

    if effective_mode == "PERCENT":
        live_mcap = impact["live_mcap"]
        if live_mcap <= 0:
            return None

        cap_ratio_5m = sum_5m / live_mcap
        cap_ratio_1h = sum_1h / live_mcap
        cap_ratio_cascade = sum_cascade / live_mcap

        has_cascade = (
            cascade_count >= config.CASCADE_TRIGGER_COUNT
            and cap_ratio_cascade >= target["threshold_cascade_mcap_pct"]
            and sum_cascade >= target["threshold_cascade_mcap_usd_min"]
        )
        has_volume = (
            cap_ratio_5m >= target["threshold_mcap_pct"]
            and sum_5m >= target["threshold_mcap_usd_min"]
        ) or (
            cap_ratio_1h >= (target["threshold_mcap_pct"] * config.VOLUME_MULTIPLIER)
            and sum_1h >= (target["threshold_mcap_usd_min"] * config.VOLUME_MULTIPLIER)
        )
    else:
        has_cascade = (
            cascade_count >= config.CASCADE_TRIGGER_COUNT
            and sum_cascade >= target["threshold_cascade"]
        )
        has_volume = (
            sum_5m >= target["threshold"]
            or sum_1h >= (target["threshold"] * config.VOLUME_MULTIPLIER)
        )

    oi_pct = market_data["oi_pct"]
    oi_val = market_data["oi_val"]
    has_oi_pump = (
        oi_pct is not None
        and oi_val is not None
        and oi_pct >= target["threshold_oi_percent"]
        and abs(oi_val) >= target["threshold_oi_value"]
    )
    has_squeeze = has_volume and sum_5m > (sum_1h * config.SQUEEZE_RATIO)

    alert_type: SignalAlertType | None = None
    alert_title = ""

    if has_cascade and target["alert_cascade"]:
        alert_type = "CASCADE"
        alert_title = f"⚡️ LIQ КАСКАД x{cascade_count}"
    elif has_oi_pump and target["alert_oi"]:
        alert_type = "OI_PUMP"
        alert_title = "📈 OI PUMP"
    elif has_squeeze and target["alert_squeeze"]:
        alert_type = "SQUEEZE"
        alert_title = "🔥 QUICK SQUEEZE"
    elif has_volume and target["alert_volume"]:
        alert_type = "VOLUME"
        alert_title = "📊 LIQ VOLUME"

    if alert_type is None:
        return None

    history_key = (target["id"], dto["symbol"], side_label)
    last_alert = user_alert_history.get(history_key)
    if last_alert:
        if (now - last_alert["time"]).total_seconds() < config.GLOBAL_COOLDOWN_SEC:
            return None

        if alert_type in ["VOLUME", "SQUEEZE"]:
            grew_enough = sum_5m >= last_alert["sum_5m"] * config.ALERT_GROWTH_PERCENTAGE
            if not grew_enough:
                return None

    user_alert_history[history_key] = {
        "time": now,
        "sum_5m": sum_5m,
    }

    return {
        "alert_title": alert_title,
        "alert_type": alert_type,
        "threshold_cascade": target["threshold_cascade"],
        "show_oi": target["alert_oi"],
        "show_cvd": target["alert_cvd"],
        "show_rsi": target["alert_rsi"],
        "used_mcap": used_mcap,
    }


class MessengerWorker:
    def __init__(self) -> None:
        self.consumer_name = os.getenv("HOSTNAME") or f"messenger-{os.getpid()}"
        self.bot: Bot | None = None
        self._cached_users: list[CachedAlertTarget] = []
        self._cache_lock = asyncio.Lock()

    async def _create_bot(self) -> Bot:
        session = None
        if config.PROXY_URL:
            from aiogram.client.session.aiohttp import AiohttpSession
            session = AiohttpSession(proxy=config.PROXY_URL)
        return Bot(token=config.BOT_TOKEN, session=session)

    async def _load_cache(self) -> None:
        async with async_session() as session:
            cached_targets: list[CachedAlertTarget] = []

            active_users = await get_active_users(session, force_refresh=True)
            for user in active_users:
                cached_targets.append(_build_cached_target(user, user.id))

            if config.PRIVATE_CHANNEL_ID is not None:
                channel_settings = await ChannelService.get_settings(session)
                if channel_settings and channel_settings.is_active:
                    cached_targets.append(_build_cached_target(channel_settings, "CHANNEL"))

        async with self._cache_lock:
            self._cached_users = cached_targets

        logger.info("Кэш messenger worker обновлен: %s адресатов.", len(cached_targets))

    async def _refresh_single_target(self, raw_target_id: str) -> None:
        if raw_target_id in {"ALL", "*", "CHANNEL"}:
            await self._load_cache()
            return

        try:
            user_id = int(raw_target_id)
        except ValueError:
            logger.warning("Получен некорректный payload инвалидации: %s", raw_target_id)
            return

        async with async_session() as session:
            user = await get_user_by_id(session, user_id)

        async with self._cache_lock:
            self._cached_users = [
                target for target in self._cached_users
                if target["id"] != user_id
            ]
            if user is not None and _is_user_active(user):
                self._cached_users.append(_build_cached_target(user, user_id))

        logger.info("Локальный кэш messenger worker обновлен для user_id=%s.", user_id)

    async def _get_targets_snapshot(self) -> list[CachedAlertTarget]:
        async with self._cache_lock:
            return list(self._cached_users)

    async def _cache_refresher_task(self) -> None:
        while True:
            try:
                await self._load_cache()
            except Exception:
                logger.exception("Ошибка периодического обновления кэша messenger worker.")
            await asyncio.sleep(60)

    async def _cache_invalidation_listener(self) -> None:
        while True:
            pubsub = None
            try:
                redis = await redis_bus.get_redis_connection()
                pubsub = redis.pubsub()
                await pubsub.subscribe(config.REDIS_CACHE_INVALIDATION_CHANNEL)
                logger.info(
                    "Подписка на Redis Pub/Sub активирована: %s",
                    config.REDIS_CACHE_INVALIDATION_CHANNEL,
                )

                while True:
                    message = await pubsub.get_message(
                        ignore_subscribe_messages=True,
                        timeout=1.0,
                    )
                    if message is None:
                        await asyncio.sleep(0.1)
                        continue

                    raw_data = message.get("data")
                    payload = (
                        raw_data.decode("utf-8")
                        if isinstance(raw_data, bytes)
                        else str(raw_data)
                    )
                    await self._refresh_single_target(payload)
            except Exception:
                logger.exception("Ошибка подписки cache invalidation в messenger worker.")
                await asyncio.sleep(1)
            finally:
                if pubsub is not None:
                    await pubsub.close()

    async def _dispatch_batches(self, alert_tasks: list[Any]) -> None:
        batch_size = 50
        for i in range(0, len(alert_tasks), batch_size):
            batch = alert_tasks[i:i + batch_size]
            await asyncio.gather(*batch, return_exceptions=True)
            await asyncio.sleep(0.01)

    async def _cleanup_alert_history_task(self) -> None:
        while True:
            await asyncio.sleep(3600)
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            threshold = now.timestamp() - 86400
            keys_to_delete = [
                key
                for key, data in user_alert_history.items()
                if data["time"].timestamp() < threshold
            ]
            for key in keys_to_delete:
                del user_alert_history[key]

    async def _process_signal(self, dto: SignalDTO) -> None:
        if self.bot is None:
            raise RuntimeError("Messenger worker bot is not initialized.")

        targets = await self._get_targets_snapshot()
        prepared_alerts: list[tuple[int, dict[str, Any]]] = []

        for target in targets:
            try:
                trigger_result = _check_triggers_from_dto(target, dto)
            except Exception:
                logger.exception("Ошибка фильтрации сигнала для target=%s", target["id"])
                continue

            if trigger_result is None:
                continue

            if target["id"] == "CHANNEL":
                if config.PRIVATE_CHANNEL_ID is None:
                    logger.info("PRIVATE_CHANNEL_ID не задан. Отправка сигнала в канал пропущена.")
                    continue
                recipient_id = int(config.PRIVATE_CHANNEL_ID)
            else:
                recipient_id = int(target["id"])
            payload = build_alert_payload(
                dto,
                threshold_cascade=trigger_result["threshold_cascade"],
                settings_override={
                    "show_oi": trigger_result["show_oi"],
                    "show_cvd": trigger_result["show_cvd"],
                    "show_rsi": trigger_result["show_rsi"],
                    "used_mcap": trigger_result["used_mcap"],
                },
                alert_type=trigger_result["alert_type"],
                alert_title=trigger_result["alert_title"],
            )
            prepared_alerts.append((recipient_id, payload))

        if not prepared_alerts:
            return

        await self._dispatch_batches([
            send_liquidation_alert(
                self.bot,
                recipient_id,
                photo_file_id=dto["chart_file_id"],
                **payload,
            )
            for recipient_id, payload in prepared_alerts
        ])

    async def run(self) -> None:
        self.bot = await self._create_bot()
        await self._load_cache()
        await redis_bus.create_consumer_group_for_stream(
            stream_name=config.REDIS_READY_STREAM_NAME,
            group_name=config.REDIS_MESSENGER_CONSUMER_GROUP,
        )

        cache_task = asyncio.create_task(self._cache_refresher_task())
        invalidation_task = asyncio.create_task(self._cache_invalidation_listener())
        cleanup_task = asyncio.create_task(self._cleanup_alert_history_task())

        try:
            logger.info("Messenger worker запущен как consumer=%s", self.consumer_name)
            while True:
                signals = await redis_bus.get_signals_from_stream(
                    consumer_name=self.consumer_name,
                    stream_name=config.REDIS_READY_STREAM_NAME,
                    group_name=config.REDIS_MESSENGER_CONSUMER_GROUP,
                )
                if not signals:
                    continue

                for message_id, dto in signals:
                    try:
                        await self._process_signal(dto)
                        await redis_bus.ack_signal_for_stream(
                            message_id=message_id,
                            stream_name=config.REDIS_READY_STREAM_NAME,
                            group_name=config.REDIS_MESSENGER_CONSUMER_GROUP,
                        )
                    except Exception:
                        logger.exception(
                            "Ошибка обработки сигнала %s в messenger worker.",
                            message_id,
                        )
        finally:
            cache_task.cancel()
            invalidation_task.cancel()
            cleanup_task.cancel()
            await asyncio.gather(
                cache_task,
                invalidation_task,
                cleanup_task,
                return_exceptions=True,
            )
            await self.bot.session.close()


async def main() -> None:
    setup_logging()
    worker = MessengerWorker()
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
