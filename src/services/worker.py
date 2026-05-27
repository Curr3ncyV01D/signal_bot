import asyncio
import logging
from aiogram import Bot
from src.core.config import config
from src.database.session import async_session
from src.database.crud.liq_service import save_liquidation
from src.services.analyzer import process_liquidation_item

logger = logging.getLogger(__name__)

class DataWorker:
    def __init__(self, bot: Bot,
    liq_aggregator, 
    market_aggregator, 
    trade_aggregator):
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
                    await self._handle_liquidation(data)
                
                elif msg_type == "ticker":
                    # data здесь — это список или объект тикера
                    # Bybit V5 ticker шлет: 'lastPrice', 'openInterestValue', 'fundingRate'
                    symbol = data.get("s")
                    price = float(data.get("lastPrice", 0))
                    oi = float(data.get("openInterestValue", 0))
                    funding = float(data.get("fundingRate", 0))
                    self.market_aggregator.update(symbol, price, oi, funding)

                elif msg_type == "trade":
                    # data здесь — список сделок
                    symbol = msg.get("topic", "").split(".")[-1]
                    self.trade_aggregator.add_trades(symbol, data)

                queue.task_done()
            except Exception as e:
                logger.error(f"Ошибка воркера: {e}")
                queue.task_done()

    async def _handle_liquidation(self, item: dict):
        """Логика обработки ликвидаций"""
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

        side_label = "LONG" if raw_side == "Buy" else "SHORT"
        
        # 1. Добавляем в инстанс агрегатора (DI)
        self.liq_aggregator.add_event(symbol, value, side_label)

        # 2. Работа с БД и Анализатором
        async with async_session() as session:
            await save_liquidation(session, item)
            # Передаем инстанс агрегатора в анализатор
            await process_liquidation_item(session, symbol, side_label, self.bot, self.liq_aggregator, self.market_aggregator, self.trade_aggregator)