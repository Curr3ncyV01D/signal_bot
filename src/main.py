import asyncio
import logging
import signal
from aiogram import Bot, Dispatcher
from sqlalchemy import select

from src.core.config import config
from src.core.security import SecurityManager
from src.database.session import async_session
from src.database.models import User
from src.database.crud.liq_service import get_recent_liquidations
from src.database.crud.channel_service import ChannelService
from src.bot.handlers import main_router as router
from src.bot.middlewares.block_middleware import BlockMiddleware
from src.services.bybit_ws import BybitListener
from src.services.aggregators.liq_aggregator import LiquidationAggregator
from src.services.aggregators.market_aggregator import MarketAggregator
from src.services.aggregators.trade_aggregator import TradeAggregator
from src.services.analyzer import cleanup_alert_history_task
from src.services.worker import DataWorker
from src.services.retention import retention_policy_worker
from src.services.warmup import warmup_system
from src.services.bouncer import bouncer_worker
from src.services.dashboard import dashboard_worker
from src.services.payment_worker import payment_checker_worker
from src.services.cryptopay import cryptopay
from src.services.symbol_sync import build_target_symbols, symbol_sync_worker
from src.utils import lag_detector

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
    
    # Инициализация бота
    bot = Bot(token=config.BOT_TOKEN, session=session)
    dp = Dispatcher()
    dp.update.outer_middleware(BlockMiddleware(async_session))
    dp.include_router(router)

    # Инициализация инфраструктуры данных (SOLID & DI)
    liq_aggregator = LiquidationAggregator()
    market_aggregator = MarketAggregator()
    trade_aggregator = TradeAggregator()

    queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    # 0. Инициализация кеша безопасности (заблокированные пользователи)
    async with async_session() as session_db:
        blocked_query = select(User.id).where(User.is_blocked == True)
        blocked_result = await session_db.execute(blocked_query)
        for user_id in blocked_result.scalars():
            SecurityManager.block(user_id)
    logging.info(f"🛡️ SecurityManager инициализирован: {len(SecurityManager.blocked_users)} заблокированных пользователей.")

    # 1. Получаем список монет для DEV/PROD режима до старта WS 
    listener = BybitListener(queue, loop)
    all_symbols = await asyncio.to_thread(listener.get_all_usdt_symbols)
    target_symbols = build_target_symbols(all_symbols)

    # 2. Прогрев ликвидаций из БД 
    logging.info("Прогрев ликвидаций из базы данных...")
    async with async_session() as session_db:
        historical_data = await get_recent_liquidations(session_db, minutes=60)
        liq_aggregator.load_historical_data(historical_data)

        await ChannelService.get_settings(session_db)
        logging.info("⚙️ Настройки канала успешно загружены в кэш.")

    # 3. Принудительный прогрев ОИ и RSI из Bybit API 
    await warmup_system(market_aggregator, target_symbols)

    # 4. Передаем прогретые монеты в листенер и запускаем сокеты 
    listener.target_symbols = target_symbols
    await listener.start()

    # 5. Запускаем Диспетчер-Воркер с внедрением всех трех агрегаторов 
    worker = DataWorker(
        bot=bot, 
        liq_aggregator=liq_aggregator, 
        market_aggregator=market_aggregator, 
        trade_aggregator=trade_aggregator 
    )
    worker_task = asyncio.create_task(worker.run(queue))
    sync_task = asyncio.create_task(symbol_sync_worker(listener, market_aggregator))

    # 6. Запускаем фоновые задачи очистки и Вышибалу
    lag_detector_task = asyncio.create_task(lag_detector())
    retention_task = asyncio.create_task(retention_policy_worker(hours=4))
    aggregator_task = asyncio.create_task(liq_aggregator.cleanup_task())
    alert_cleanup_task = asyncio.create_task(cleanup_alert_history_task())        
    bouncer_task = asyncio.create_task(bouncer_worker(bot, interval_minutes=15))
    dashboard_task = asyncio.create_task(dashboard_worker(bot, liq_aggregator, market_aggregator))
    payment_task = asyncio.create_task(payment_checker_worker(bot))

    # Передаем зависимости в Polling для команды /status 
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
                trade_aggregator=trade_aggregator,
                data_queue=queue 
            )
        )
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
            [lag_detector_task, worker_task, sync_task, retention_task, aggregator_task, alert_cleanup_task, bouncer_task, dashboard_task, payment_task]
        )

async def on_shutdown(bot: Bot, listener: BybitListener, tasks: list[asyncio.Task]):
    logging.info("Завершение работы...")
    
    for task in tasks:
        task.cancel()
    
    # Даем время сокетам aiohttp закрыться 
    await asyncio.sleep(0.5)
    
    try:
        await asyncio.gather(*tasks, return_exceptions=True)
    except asyncio.CancelledError:
        pass

    if listener:
        try:
            listener.stop()
        except Exception as e:
            logging.error(f"Ошибка при закрытии WebSocket: {e}")

    await cryptopay.close()
    await bot.session.close()
    logging.info("Все соединения закрыты.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
