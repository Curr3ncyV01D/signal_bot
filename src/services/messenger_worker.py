import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, TypedDict, cast

import orjson

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter

from src.bot.notifier import build_alert_payload, send_liquidation_alert
from src.core.config import config, setup_logging
from src.core.dto import SignalAlertType, SignalDTO
from src.core.redis_bus import LockResult, redis_bus
from src.database.crud.channel_service import ChannelService
from src.database.crud.user_service import get_active_users, get_user_by_id
from src.database.functions import get_utc_now
from src.database.session import async_session
from src.services.asset_manager import (
    AssetManager,
    PLACEHOLDER_MSG_ID_REDIS_KEY,
)
from src.services.logic.trigger_engine import (
    build_alert_title,
    evaluate_trigger_logic,
    is_signal_spammy,
)

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
    time: float
    sum_5m: float


class TriggerResult(TypedDict):
    alert_title: str
    alert_type: SignalAlertType
    threshold_cascade: float
    show_oi: bool
    show_cvd: bool
    show_rsi: bool
    used_mcap: bool


def _msg_history_redis_key(target_id: int | str, symbol: str, side_label: str) -> str:
    return f"csl:msg:history:{target_id}:{symbol}:{side_label}"


def _decode_redis_payload(payload: bytes | str | None) -> bytes | None:
    if payload is None:
        return None
    if isinstance(payload, bytes):
        return payload
    return payload.encode("utf-8")


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


async def _check_triggers_from_dto(
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
    now_ts = now.timestamp()
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

        cascade_threshold = target["threshold_cascade_mcap_pct"]
        if (
            cap_ratio_cascade < target["threshold_cascade_mcap_pct"]
            or sum_cascade < target["threshold_cascade_mcap_usd_min"]
        ):
            cascade_threshold = float("inf")

        volume_threshold = target["threshold_mcap_pct"]
        has_volume_floor = (
            cap_ratio_5m >= target["threshold_mcap_pct"]
            and sum_5m >= target["threshold_mcap_usd_min"]
        ) or (
            cap_ratio_1h >= (target["threshold_mcap_pct"] * config.VOLUME_MULTIPLIER)
            and sum_1h >= (target["threshold_mcap_usd_min"] * config.VOLUME_MULTIPLIER)
        )
        if not has_volume_floor:
            volume_threshold = float("inf")
    else:
        cascade_threshold = target["threshold_cascade"]
        volume_threshold = target["threshold"]

    alert_type = evaluate_trigger_logic(
        sum_5m=sum_5m,
        sum_1h=sum_1h,
        sum_cascade=sum_cascade,
        cascade_count=cascade_count,
        oi_pct=market_data["oi_pct"],
        oi_val=market_data["oi_val"],
        volume_threshold=volume_threshold,
        cascade_threshold=cascade_threshold,
        oi_threshold_pct=target["threshold_oi_percent"],
        oi_threshold_value=target["threshold_oi_value"],
        cascade_trigger_count=config.CASCADE_TRIGGER_COUNT,
        volume_multiplier=config.VOLUME_MULTIPLIER,
        squeeze_ratio=config.SQUEEZE_RATIO,
        enable_cascade=target["alert_cascade"],
        enable_oi=target["alert_oi"],
        enable_squeeze=target["alert_squeeze"],
        enable_volume=target["alert_volume"],
    )
    if alert_type is None:
        return None
    alert_title = build_alert_title(alert_type, cascade_count)

    history_key = _msg_history_redis_key(target["id"], dto["symbol"], side_label)
    raw_last_alert = _decode_redis_payload(await redis_bus.get_key(history_key))
    if raw_last_alert is not None:
        try:
            last_alert = cast(AlertHistoryEntry, orjson.loads(raw_last_alert))
        except Exception:
            last_alert = None
        if last_alert is not None and is_signal_spammy(
            last_time=float(last_alert.get("time", 0.0)),
            current_time=now_ts,
            last_sum=float(last_alert.get("sum_5m", 0.0)),
            current_sum=sum_5m,
            cooldown_limit=config.GLOBAL_COOLDOWN_SEC,
            growth_multiplier=config.ALERT_GROWTH_PERCENTAGE,
        ):
            return None

    await redis_bus.set_key(
        history_key,
        orjson.dumps({"time": now_ts, "sum_5m": sum_5m}).decode("utf-8"),
        expire_seconds=3600,
    )

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
        self._resolve_semaphore = asyncio.Semaphore(3)
        self.placeholder_msg_id: int | None = None
        self._resolved_file_ids: dict[int, str] = {}

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

    @staticmethod
    def _decode_redis_value(value: bytes | str | None) -> str | None:
        if value is None:
            return None
        return value.decode("utf-8") if isinstance(value, bytes) else str(value)

    async def _load_placeholder_message_id_from_redis(self) -> str | None:
        return self._decode_redis_value(await redis_bus.get_key(PLACEHOLDER_MSG_ID_REDIS_KEY))

    async def _load_placeholder_message_id(self) -> int | None:
        if self.placeholder_msg_id is None:
            message_id = await self._load_placeholder_message_id_from_redis()
            if message_id is None:
                async with async_session() as session:
                    message_id = await AssetManager.get_placeholder_metadata(session)

            if message_id is not None:
                self.placeholder_msg_id = int(message_id)
                await redis_bus.set_key(PLACEHOLDER_MSG_ID_REDIS_KEY, message_id)

        return self.placeholder_msg_id

    def _remember_resolved_file_id(self, message_id: int, file_id: str) -> None:
        self._resolved_file_ids[message_id] = file_id
        if len(self._resolved_file_ids) > 5000:
            logger.warning("L1 media cache переполнен. Выполняю очистку RAM-кэша resolve.")
            self._resolved_file_ids.clear()
            self._resolved_file_ids[message_id] = file_id

    async def _recover_placeholder_message_id(self) -> int | None:
        if self.bot is None:
            raise RuntimeError("Messenger worker bot is not initialized.")

        logger.warning("Placeholder в LOG_CHANNEL_ID отсутствует. Запускаю восстановление ассета.")
        self.placeholder_msg_id = None
        async with async_session() as session:
            restored_message_id = await AssetManager.ensure_placeholder(self.bot, session)

        if restored_message_id is not None:
            self.placeholder_msg_id = restored_message_id
        return restored_message_id

    async def _resolve_media_to_file_id(self, message_id: int) -> str | None:
        if self.bot is None:
            raise RuntimeError("Messenger worker bot is not initialized.")

        cached_file_id = self._resolved_file_ids.get(message_id)
        if cached_file_id is not None:
            return cached_file_id

        redis_key = f"csl:file_id:{self.bot.id}:{message_id}"
        cached_redis = self._decode_redis_value(await redis_bus.get_key(redis_key))
        if cached_redis is not None:
            self._remember_resolved_file_id(message_id, cached_redis)
            return cached_redis

        if config.LOG_CHANNEL_ID is None:
            return None

        lock_key = f"csl:lock:resolve:{self.bot.id}:{message_id}"
        lock_token: str | None = None

        while True:
            lock_result, lock_token = await redis_bus.acquire_lock(lock_key, ttl=10)
            if lock_result is LockResult.ACQUIRED:
                break
            if lock_result is LockResult.ERROR:
                await asyncio.sleep(1)
            else:
                await asyncio.sleep(0.5)

            cached_redis = self._decode_redis_value(await redis_bus.get_key(redis_key))
            if cached_redis is not None:
                self._remember_resolved_file_id(message_id, cached_redis)
                return cached_redis

        tmp_msg = None
        try:
            cached_file_id = self._resolved_file_ids.get(message_id)
            if cached_file_id is not None:
                return cached_file_id

            cached_redis = self._decode_redis_value(await redis_bus.get_key(redis_key))
            if cached_redis is not None:
                self._remember_resolved_file_id(message_id, cached_redis)
                return cached_redis

            async with self._resolve_semaphore:
                tmp_msg = await self.bot.forward_message(
                    chat_id=int(config.LOG_CHANNEL_ID),
                    from_chat_id=int(config.LOG_CHANNEL_ID),
                    message_id=message_id,
                    disable_notification=True,
                )
            file_id = tmp_msg.photo[-1].file_id if tmp_msg.photo else None
            if file_id is None:
                logger.error("Forward resolve не вернул photo для message_id=%s", message_id)
                return None

            self._remember_resolved_file_id(message_id, file_id)
            await redis_bus.set_key(redis_key, file_id, 86400)
            return file_id
        except TelegramRetryAfter as exc:
            logger.warning(
                "Telegram RetryAfter при resolve message_id=%s. Ожидаю %s сек.",
                message_id,
                exc.retry_after,
            )
            await asyncio.sleep(exc.retry_after)
            return await self._resolve_media_to_file_id(message_id)
        except TelegramBadRequest as exc:
            error_text = str(exc).lower()
            if "message to forward not found" in error_text:
                if message_id == self.placeholder_msg_id:
                    restored_message_id = await self._recover_placeholder_message_id()
                    if restored_message_id is not None and restored_message_id != message_id:
                        return await self._resolve_media_to_file_id(restored_message_id)
                logger.warning(
                    "Сообщение для forward-resolve не найдено message_id=%s. Перехожу в fallback.",
                    message_id,
                )
                return None
            logger.error("Сообщение для forward-resolve недоступно message_id=%s: %s", message_id, exc)
            return None
        except Exception:
            logger.exception("Не удалось зарезолвить media file_id для message_id=%s", message_id)
            return None
        finally:
            if tmp_msg is not None:
                try:
                    await self.bot.delete_message(int(config.LOG_CHANNEL_ID), tmp_msg.message_id)
                except Exception:
                    logger.warning("Не удалось удалить временное forwarded message_id=%s", tmp_msg.message_id)
            if lock_token is not None:
                await redis_bus.release_lock(lock_key, lock_token)

    async def _process_signal(self, dto: SignalDTO) -> None:
        if self.bot is None:
            raise RuntimeError("Messenger worker bot is not initialized.")

        target_msg_id = dto["chart_message_id"]
        if target_msg_id is None:
            target_msg_id = await self._load_placeholder_message_id()

        photo_file_id = None
        if target_msg_id is not None:
            photo_file_id = await self._resolve_media_to_file_id(target_msg_id)
        targets = await self._get_targets_snapshot()
        prepared_alerts: list[tuple[int, dict[str, Any]]] = []

        for target in targets:
            try:
                trigger_result = await _check_triggers_from_dto(target, dto)
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
                photo_file_id=photo_file_id,
                **payload,
            )
            for recipient_id, payload in prepared_alerts
        ])

    async def run(self) -> None:
        self.bot = await self._create_bot()
        await self._load_cache()
        placeholder_msg_id = await self._load_placeholder_message_id()
        if placeholder_msg_id is not None:
            await self._resolve_media_to_file_id(placeholder_msg_id)
        await redis_bus.create_consumer_group_for_stream(
            stream_name=config.REDIS_READY_STREAM_NAME,
            group_name=config.REDIS_MESSENGER_CONSUMER_GROUP,
        )

        cache_task = asyncio.create_task(self._cache_refresher_task())
        invalidation_task = asyncio.create_task(self._cache_invalidation_listener())

        try:
            logger.info("Messenger worker запущен как consumer=%s", self.consumer_name)
            while True:
                try:
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
                except Exception:
                    logger.exception("Критическая ошибка основного цикла messenger worker.")
                    await asyncio.sleep(1)
        finally:
            cache_task.cancel()
            invalidation_task.cancel()
            await asyncio.gather(
                cache_task,
                invalidation_task,
                return_exceptions=True,
            )
            await self.bot.session.close()


async def main() -> None:
    setup_logging()
    worker = MessengerWorker()
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
