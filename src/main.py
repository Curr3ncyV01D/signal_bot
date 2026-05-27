import asyncio
import logging
import signal
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession

from src.core.config import config
from src.database.session import async_session
from src.database.crud.liq_service import get_recent_liquidations
from src.bot.handlers import router
from src.services.bybit_ws import BybitListener
from src.services.aggregators.liq_aggregator import LiquidationAggregator
from src.services.aggregators.market_aggregator import MarketAggregator
from src.services.aggregators.trade_aggregator import TradeAggregator
from src.services.analyzer import cleanup_alert_history_task
from src.services.worker import DataWorker
from src.services.retention import retention_policy_worker

async def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.getLogger('pybit').setLevel(logging.WARNING)
    logging.getLogger('websocket').setLevel(logging.WARNING)

    # Логика прокси
    session = None
    if config.PROXY_URL:
        from aiogram.client.session.aiohttp import AiohttpSession
        session = AiohttpSession(proxy=config.PROXY_URL)
        logging.info(f"📡 Запуск с прокси: {config.PROXY_URL}")
    else:
        logging.info("🌐 Запуск без прокси (прямое соединение)")
    
    # 1. Инициализация бота
    bot = Bot(token=config.BOT_TOKEN, session=session)
    dp = Dispatcher()
    dp.include_router(router)

    # 2. Инициализируем агрегаторы
    liq_aggregator = LiquidationAggregator()
    market_aggregator = MarketAggregator() 
    trade_aggregator = TradeAggregator()


    # 3. Инициализация инфраструктуры данных
    queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    # 4. Прогрев Кэша
    logging.info("Прогрев оперативной памяти из базы данных...")
    async with async_session() as session:
        historical_data = await get_recent_liquidations(session, minutes=60)
        liq_aggregator.load_historical_data(historical_data)
    
    # 5. Инициализируем Диспетчер-Воркер
    worker = DataWorker(
        bot=bot, 
        liq_aggregator=liq_aggregator,
        market_aggregator=market_aggregator,
        trade_aggregator=trade_aggregator)
    worker_task = asyncio.create_task(worker.run(queue))

    # 6. Producer (Bybit)
    listener = BybitListener(queue, loop)
    listener.start()

    # 7. Фоновые задачи
    # Retention Policy (Очистка устаревших данных из БД)
    retention_task = asyncio.create_task(retention_policy_worker(hours=4, interval_hours=4))
    # Очистка аггрегатора
    aggregator_task = asyncio.create_task(liq_aggregator.cleanup_task())
    # Очистка истории алертов
    alert_cleanup_task = asyncio.create_task(cleanup_alert_history_task())        

    stop_event = asyncio.Event()

    def signal_handler():
        logging.info("Получен сигнал завершения...")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, signal_handler)
        except NotImplementedError:
            pass

    logging.info("Система запущена в модульном режиме.")

    try:
        polling_task = asyncio.create_task(
            dp.start_polling(
                bot, 
                listener=listener,
                liq_aggregator=liq_aggregator,
                market_aggregator=market_aggregator,
                trade_aggregator=trade_aggregator))

        stop_task = asyncio.create_task(stop_event.wait())
        
        done, pending = await asyncio.wait(
            [polling_task, stop_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        if polling_task in pending:
            await dp.stop_polling()
        
        await polling_task
        
        if stop_task in pending:
            stop_task.cancel()
            
    except Exception as e:
        logging.error(f"Ошибка в основном цикле: {e}")
    finally:
        await on_shutdown(
            bot, 
            listener, 
            [worker_task, retention_task, aggregator_task, alert_cleanup_task]
        )

async def on_shutdown(bot: Bot, listener: BybitListener, tasks: list[asyncio.Task]):
    logging.info("Завершение работы...")
    
    # Массово останавливаем всех воркеров
    for task in tasks:
        task.cancel()
    
    try:
        await asyncio.gather(*tasks, return_exceptions=True)
    except asyncio.CancelledError:
        pass

    # Закрываем WebSocket
    if listener:
        try:
            listener.stop() 
        except Exception as e:
            logging.error(f"Ошибка при закрытии WebSocket: {e}")

    # Закрываем сессию бота
    await bot.session.close()
    logging.info("Все соединения закрыты.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass