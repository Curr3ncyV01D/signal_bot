import asyncio
import logging
from aiogram import Bot
from src.core.config import config
from src.database.session import async_session
from src.database.crud.liq_service import save_liquidation
from src.services.analyzer import process_liquidation_item
from src.services.aggregator import aggregator

async def database_worker(queue: asyncio.Queue, bot: Bot):
    logging.info("Consumer (DB Worker) запущен.")
    
    while True:
        try:
            item = await queue.get()
            
            # 1. Извлекаем данные
            symbol = item.get("s") or item.get("symbol")
            raw_side = item.get("S") or item.get("side")
            price = float(item.get("p") or item.get("price", 0))
            qty = float(item.get("v") or item.get("qty", 0))
            value = round(price * qty, 2)
            
            # 2. Проверка на минимальный объем и игнорирование некоторых пар
            if not symbol or value <= config.MIN_LIQ_VALUE_FILTER or symbol in config.IGNORED_SYMBOLS:
                queue.task_done()
                continue

            # Определяем тип ликвидации (Buy ордер закрывает Short позицию)
            side_label = "LONG" if raw_side == "Buy" else "SHORT"
            
            # 2. Добавляем в оперативную память
            aggregator.add_event(symbol, value, side_label)

            # 3. Сохраняем в БД (архив) и передаем в анализатор
            async with async_session() as session:
                await save_liquidation(session, item)
                
                await process_liquidation_item(session, symbol, side_label, bot)
            
            queue.task_done()
        except Exception as e:
            logging.error(f"Критическая ошибка в воркере: {e}", exc_info=True)
            try:
                queue.task_done()
            except ValueError:
                pass
            await asyncio.sleep(1)