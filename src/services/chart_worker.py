import asyncio
import logging
import os
import time
from time import monotonic

from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter
from aiogram.types import BufferedInputFile

from src.core.config import config, setup_logging
from src.core.dto import SignalDTO
from src.core.redis_bus import redis_bus
from src.services import chart_generator
from src.utils import strip_emojis

logger = logging.getLogger(__name__)


class ChartWorker:
    def __init__(self) -> None:
        self.consumer_name = os.getenv("HOSTNAME") or f"artist-{os.getpid()}"
        self.bot: Bot | None = None
        self._locks: dict[str, asyncio.Lock] = {}
        self._lock_last_used: dict[str, float] = {}
        self._lock_refs: dict[str, int] = {}
        self._locks_guard = asyncio.Lock()
        self._tokens = float(config.CHART_BUCKET_CAPACITY)
        self._last_refill_ts = monotonic()
        self._mute_until = 0.0

    async def _create_bot(self) -> Bot:
        session = None
        if config.PROXY_URL:
            from aiogram.client.session.aiohttp import AiohttpSession

            session = AiohttpSession(proxy=config.PROXY_URL)
        return Bot(token=config.BOT_TOKEN, session=session)

    @staticmethod
    def _chart_cache_key(symbol: str) -> str:
        return f"{config.REDIS_CHART_CACHE_PREFIX}:{symbol}"

    def _refill_tokens(self) -> None:
        now = monotonic()
        delta = now - self._last_refill_ts
        if delta <= 0:
            return
        self._tokens = min(
            float(config.CHART_BUCKET_CAPACITY),
            self._tokens + (delta * float(config.CHART_BUCKET_REFILL_RATE)),
        )
        self._last_refill_ts = now

    def _should_consume_token(self, alert_type: str, sum_5m: float) -> tuple[bool, str | None]:
        self._refill_tokens()
        now = monotonic()
        if now < self._mute_until:
            return False, "mute"

        is_critical = alert_type == "CASCADE"
        is_priority = alert_type == "SQUEEZE" or sum_5m > float(config.CHART_PRIORITY_VOLUME_USD)

        if self._tokens < 1.0:
            return False, "empty"
        if self._tokens < float(config.CHART_CRITICAL_THRESHOLD) and not is_critical:
            return False, "critical_only"
        if self._tokens < float(config.CHART_PRIORITY_THRESHOLD) and not (is_critical or is_priority):
            return False, "priority_only"

        self._tokens -= 1.0
        return True, None

    async def _reserve_symbol_lock(self, symbol: str) -> asyncio.Lock:
        async with self._locks_guard:
            symbol_lock = self._locks.get(symbol)
            if symbol_lock is None:
                symbol_lock = asyncio.Lock()
                self._locks[symbol] = symbol_lock
            self._lock_last_used[symbol] = monotonic()
            self._lock_refs[symbol] = self._lock_refs.get(symbol, 0) + 1
            return symbol_lock

    async def _release_symbol_lock(self, symbol: str) -> None:
        async with self._locks_guard:
            self._lock_last_used[symbol] = monotonic()
            remaining_refs = self._lock_refs.get(symbol, 0) - 1
            if remaining_refs > 0:
                self._lock_refs[symbol] = remaining_refs
            else:
                self._lock_refs.pop(symbol, None)

    async def _cleanup_symbol_locks_task(self) -> None:
        lock_ttl_seconds = 4 * 3600
        while True:
            try:
                await asyncio.sleep(3600)
                now = monotonic()
                async with self._locks_guard:
                    expired_symbols = [
                        symbol
                        for symbol, last_used in self._lock_last_used.items()
                        if (now - last_used) >= lock_ttl_seconds
                        and self._lock_refs.get(symbol, 0) == 0
                        and not self._locks[symbol].locked()
                    ]
                    for symbol in expired_symbols:
                        self._locks.pop(symbol, None)
                        self._lock_last_used.pop(symbol, None)
                        self._lock_refs.pop(symbol, None)
            except Exception:
                logger.exception("Ошибка cleanup локов chart worker.")
                await asyncio.sleep(1)

    @staticmethod
    def _dto_to_ohlc_records(dto: SignalDTO) -> list[chart_generator.OhlcRecord]:
        records: list[chart_generator.OhlcRecord] = []
        for row in dto["ohlc_history"]:
            if len(row) != 6:
                continue
            t, o, h, l, c, v = row
            records.append(
                {
                    "t": int(t),
                    "o": float(o),
                    "h": float(h),
                    "l": float(l),
                    "c": float(c),
                    "v": float(v),
                }
            )
        return records

    async def _harvest_chart_message_id(self, dto: SignalDTO, chart_bytes: bytes) -> int | None:
        if config.LOG_CHANNEL_ID is None:
            logger.info("LOG_CHANNEL_ID не задан. Harvest message_id пропущен.")
            return None

        if self.bot is None:
            raise RuntimeError("Artist bot is not initialized.")

        try:
            sent_msg = await self.bot.send_photo(
                chat_id=int(config.LOG_CHANNEL_ID),
                photo=BufferedInputFile(chart_bytes, filename=f"{dto['symbol'].lower()}_chart.png"),
                caption=f"#{dto['symbol']} {dto['alert_title']}",
                protect_content=False,
                disable_notification=True,
            )
            return sent_msg.message_id
        except TelegramRetryAfter as exc:
            self._tokens = 0.0
            self._last_refill_ts = monotonic()
            self._mute_until = monotonic() + exc.retry_after + 2
            logger.warning(
                "[CIRCUIT BREAKER] Entering mute mode for %ss",
                exc.retry_after,
            )
            return None
        except Exception:
            logger.exception("Не удалось harvest message_id для %s.", dto["symbol"])
            return None

    async def _resolve_chart_message_id(self, dto: SignalDTO) -> int | None:
        symbol = dto["symbol"]
        cache_key = self._chart_cache_key(symbol)
        cached_message_id = await redis_bus.get_key(cache_key)
        if cached_message_id:
            cached_value = (
                cached_message_id.decode("utf-8")
                if isinstance(cached_message_id, bytes)
                else str(cached_message_id)
            )
            return int(cached_value)

        symbol_lock = await self._reserve_symbol_lock(symbol)
        try:
            async with symbol_lock:
                cached_message_id = await redis_bus.get_key(cache_key)
                if cached_message_id:
                    cached_value = (
                        cached_message_id.decode("utf-8")
                        if isinstance(cached_message_id, bytes)
                        else str(cached_message_id)
                    )
                    return int(cached_value)

                ohlc_records = self._dto_to_ohlc_records(dto)
                if len(ohlc_records) < 2:
                    return None

                chart_title = strip_emojis(dto["alert_title"])
                chart_bytes = await chart_generator.render_chart(symbol, ohlc_records, chart_title)
                if chart_bytes is None:
                    return None

                message_id = await self._harvest_chart_message_id(dto, chart_bytes)
                if message_id is not None:
                    await redis_bus.set_key(cache_key, str(message_id), config.CHART_CACHE_TTL_SEC)
                return message_id
        finally:
            await self._release_symbol_lock(symbol)

    @staticmethod
    def _build_ready_dto(dto: SignalDTO, chart_message_id: int | None) -> SignalDTO:
        return {
            **dto,
            "ohlc_history": [],
            "chart_message_id": chart_message_id,
        }

    async def _process_signal(self, message_id: str, dto: SignalDTO) -> None:
        if not dto["render_requested"]:
            chart_message_id = None
        else:
            signal_age_sec = max(0.0, time.time() - float(dto["timestamp"]))
            if signal_age_sec > int(config.CHART_SIGNAL_MAX_AGE_SEC):
                logger.info(
                    "[LIMITER] Skip chart for %s | Reason: Stale Signal (%ss)",
                    dto["symbol"],
                    int(signal_age_sec),
                )
                chart_message_id = None
            else:
                should_render, skip_reason = self._should_consume_token(
                    dto["alert_type"],
                    float(dto["market_data"]["sum_5m"]),
                )
                if not should_render:
                    logger.info(
                        "[LIMITER] Skip chart for %s | Reason: Low Tokens (%.1f) | Gate: %s",
                        dto["symbol"],
                        self._tokens,
                        skip_reason or "unknown",
                    )
                    chart_message_id = None
                else:
                    chart_message_id = await self._resolve_chart_message_id(dto)
        ready_dto = self._build_ready_dto(dto, chart_message_id)

        published_id = await redis_bus.publish_signal_to_stream(
            ready_dto,
            config.REDIS_READY_STREAM_NAME,
        )
        if published_id is None:
            raise RuntimeError(f"Не удалось опубликовать ready signal для {dto['signal_id']}")

        await redis_bus.ack_signal_for_stream(
            message_id=message_id,
            stream_name=config.REDIS_RAW_STREAM_NAME,
            group_name=config.REDIS_ARTIST_CONSUMER_GROUP,
        )

    async def run(self) -> None:
        self.bot = await self._create_bot()
        await redis_bus.create_consumer_group_for_stream(
            stream_name=config.REDIS_RAW_STREAM_NAME,
            group_name=config.REDIS_ARTIST_CONSUMER_GROUP,
        )
        cleanup_locks_task = asyncio.create_task(self._cleanup_symbol_locks_task())

        try:
            logger.info("Chart worker запущен как consumer=%s", self.consumer_name)
            while True:
                try:
                    signals = await redis_bus.get_signals_from_stream(
                        consumer_name=self.consumer_name,
                        stream_name=config.REDIS_RAW_STREAM_NAME,
                        group_name=config.REDIS_ARTIST_CONSUMER_GROUP,
                    )
                    if not signals:
                        continue

                    for message_id, dto in signals:
                        try:
                            await self._process_signal(message_id, dto)
                        except Exception:
                            logger.exception("Ошибка обработки raw signal %s в artist.", message_id)
                except Exception:
                    logger.exception("Критическая ошибка основного цикла chart worker.")
                    await asyncio.sleep(1)
        finally:
            cleanup_locks_task.cancel()
            await asyncio.gather(cleanup_locks_task, return_exceptions=True)
            await self.bot.session.close()


async def main() -> None:
    setup_logging()
    worker = ChartWorker()
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
