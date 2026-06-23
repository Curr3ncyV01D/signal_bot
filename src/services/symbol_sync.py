import asyncio
import logging

from src.core.config import config
from src.services.aggregators.market_aggregator import MarketAggregator
from src.services.bybit_ws import BybitListener
from src.services.warmup import warmup_system

logger = logging.getLogger(__name__)


def build_target_symbols(all_symbols: list[str]) -> list[str]:
    ignored_set = set[str](config.IGNORED_SYMBOLS)
    target_symbols = [symbol for symbol in all_symbols if symbol not in ignored_set]

    if config.DEV_MODE:
        target_symbols = target_symbols[:config.DEV_SYMBOL_LIMIT]

    return target_symbols


async def symbol_sync_worker(listener: BybitListener, market_aggregator: MarketAggregator) -> None:
    logger.info("🔄 Фоновая синхронизация листингов запущена.")

    while True:
        try:
            all_symbols = await asyncio.to_thread(listener.get_all_usdt_symbols)
            if all_symbols:
                new_all_symbols = build_target_symbols(all_symbols)
                current_symbols = set(listener.target_symbols)
                new_symbols = [symbol for symbol in new_all_symbols if symbol not in current_symbols]

                if new_symbols:
                    await warmup_system(market_aggregator, new_symbols)
                    
                    for symbol in new_symbols:
                        # Повторный прогрев конкретной монеты для гарантии перед подпиской
                        await warmup_system(market_aggregator, [symbol])
                        await listener.add_new_symbol(symbol)
                        
                    logger.info(f"🆕 Обнаружены новые монеты: {', '.join(new_symbols)}. Добавлены через Hot Swap.")
                    
            await asyncio.sleep(600) 
        except asyncio.CancelledError:
            logger.info("🛑 Фоновая синхронизация листингов остановлена.")
            raise
        except Exception as e:
            logger.error(f"Ошибка в symbol_sync_worker: {e}", exc_info=True)
            await asyncio.sleep(60)
