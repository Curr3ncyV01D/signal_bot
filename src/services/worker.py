import asyncio
import logging
from aiogram import Bot
from src.core.config import config
from src.database.session import async_session
from src.database.crud.liq_service import save_liquidation
from src.services.analyzer import process_liquidation_item

logger = logging.getLogger(__name__)

# Семафор для ограничения одновременных задач анализа (защита от OOM)
worker_semaphore = asyncio.Semaphore(100)

class DataWorker:
    def __init__(self, bot: Bot, liq_aggregator, market_aggregator, trade_aggregator):
        self.bot = bot
        self.liq_aggregator = liq_aggregator
        self.market_aggregator = market_aggregator
        self.trade_aggregator = trade_aggregator

    async def run(self, queue: asyncio.Queue):
        logger.info("Consumer (DataWorker) запущен.")
        while True:
            try:
                msg = await queue.get()
                msg_type = msg.get("type")
                data = msg.get("data")

                if msg_type == "liquidation":
                    # Запускаем обработку ликвидации в фоновой задаче, чтобы не блокировать поток данных
                    asyncio.create_task(self._handle_liquidation(data))
                
                elif msg_type == "ticker":
                    # Bybit V5 присылает данные в поле "data", которое может быть списком
                    if isinstance(data, list):
                        item = data[0] if data else {}
                    elif isinstance(data, dict):
                        item = data
                    else:
                        item = {}

                    symbol = item.get("symbol") or item.get("s")
                    
                    if not symbol:
                        queue.task_done()
                        continue

                    # Извлекаем значения только если они есть в пакете
                    price = float(item["lastPrice"]) if "lastPrice" in item and item["lastPrice"] else None
                    oi = float(item["openInterestValue"]) if "openInterestValue" in item and item["openInterestValue"] else None
                    funding = float(item["fundingRate"]) if "fundingRate" in item and item["fundingRate"] else None

                    # ТИКЕРЫ: Записываем в агрегатор ДАЖЕ ЕСЛИ символ в IGNORED_SYMBOLS (нужно для BTC в дэшборде)
                    self.market_aggregator.update(symbol, price, oi, funding)
                    
                    # ДЕБАГ: Раскомментируй строку ниже, если хочешь увидеть поток тикеров в консоли
                    logger.debug(f"Ticker update for {symbol}: P:{price} OI:{oi}")

                elif msg_type == "trade":
                    symbol = msg.get("topic", "").split(".")[-1]
                    if symbol:
                        self.trade_aggregator.add_trades(symbol, data)

                queue.task_done()
            except Exception as e:
                logger.error(f"Критическая ошибка воркера: {e}", exc_info=True)
                try:
                    queue.task_done()
                except:
                    pass

    async def _handle_liquidation(self, item: dict):
        async with worker_semaphore:
            symbol = item.get("s") or item.get("symbol")
        raw_side = item.get("S") or item.get("side")
        
        try:
            price = float(item.get("p") or item.get("price", 0))
            qty = float(item.get("v") or item.get("qty", 0))
        except (ValueError, TypeError):
            return

        value = round(price * qty, 2)
        
        if not symbol or value <= config.MIN_LIQ_VALUE_FILTER or symbol in config.IGNORED_SYMBOLS:
            return

        # Если Bybit прислал Buy - это LONG, если Sell - это SHORT
        side_label = "LONG" if raw_side == "Buy" else "SHORT"
        self.liq_aggregator.add_event(symbol, value, side_label)

        async with async_session() as session:
            await save_liquidation(session, item)
            # Запускаем анализ и обогащение
            await process_liquidation_item(
                session=session,
                symbol=symbol,
                side_label=side_label,
                bot=self.bot,
                liq_aggregator=self.liq_aggregator,
                market_aggregator=self.market_aggregator,
                trade_aggregator=self.trade_aggregator
            )