import asyncio
import logging
import os
from collections import defaultdict

from aiogram import Bot
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
        self._locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def _create_bot(self) -> Bot:
        session = None
        if config.PROXY_URL:
            from aiogram.client.session.aiohttp import AiohttpSession

            session = AiohttpSession(proxy=config.PROXY_URL)
        return Bot(token=config.BOT_TOKEN, session=session)

    @staticmethod
    def _chart_cache_key(symbol: str) -> str:
        return f"{config.REDIS_CHART_CACHE_PREFIX}:{symbol}"

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

    async def _harvest_chart_file_id(self, dto: SignalDTO, chart_bytes: bytes) -> str | None:
        if config.LOG_CHANNEL_ID is None:
            logger.info("LOG_CHANNEL_ID не задан. Harvest file_id пропущен.")
            return None

        if self.bot is None:
            raise RuntimeError("Artist bot is not initialized.")

        try:
            sent_msg = await self.bot.send_photo(
                chat_id=int(config.LOG_CHANNEL_ID),
                photo=BufferedInputFile(chart_bytes, filename=f"{dto['symbol'].lower()}_chart.png"),
                caption=f"#{dto['symbol']} {dto['alert_title']}",
                protect_content=True,
            )
            return sent_msg.photo[-1].file_id if sent_msg.photo else None
        except Exception:
            logger.exception("Не удалось harvest file_id для %s.", dto["symbol"])
            return None

    async def _resolve_chart_file_id(self, dto: SignalDTO) -> str | None:
        symbol = dto["symbol"]
        cache_key = self._chart_cache_key(symbol)
        cached_file_id = await redis_bus.get_key(cache_key)
        if cached_file_id:
            return cached_file_id.decode("utf-8") if isinstance(cached_file_id, bytes) else str(cached_file_id)

        async with self._locks[symbol]:
            cached_file_id = await redis_bus.get_key(cache_key)
            if cached_file_id:
                return cached_file_id.decode("utf-8") if isinstance(cached_file_id, bytes) else str(cached_file_id)

            ohlc_records = self._dto_to_ohlc_records(dto)
            if len(ohlc_records) < 2:
                return None

            chart_title = strip_emojis(dto["alert_title"])
            chart_bytes = await chart_generator.render_chart(symbol, ohlc_records, chart_title)
            if chart_bytes is None:
                return None

            file_id = await self._harvest_chart_file_id(dto, chart_bytes)
            if file_id:
                await redis_bus.set_key(cache_key, file_id, config.CHART_CACHE_TTL_SEC)
            return file_id

    @staticmethod
    def _build_ready_dto(dto: SignalDTO, chart_file_id: str | None) -> SignalDTO:
        return {
            **dto,
            "ohlc_history": [],
            "chart_file_id": chart_file_id,
        }

    async def _process_signal(self, message_id: str, dto: SignalDTO) -> None:
        chart_file_id = await self._resolve_chart_file_id(dto)
        ready_dto = self._build_ready_dto(dto, chart_file_id)

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

        try:
            logger.info("Chart worker запущен как consumer=%s", self.consumer_name)
            while True:
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
        finally:
            await self.bot.session.close()


async def main() -> None:
    setup_logging()
    worker = ChartWorker()
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
