import asyncio
import logging

from src.core.config import config
from src.services.aggregators.market_aggregator import MarketAggregator
from src.services.bybit_ws import BybitListener
from src.services.warmup import warmup_system

logger = logging.getLogger(__name__)


def build_target_symbols(all_symbols: list[str]) -> list[str]:
    ignored_set = set(config.IGNORED_SYMBOLS)
    target_symbols = [symbol for symbol in all_symbols if symbol not in ignored_set]

    if config.DEV_MODE:
        target_symbols = target_symbols[:config.DEV_SYMBOL_LIMIT]

    return target_symbols


async def symbol_sync_worker(listener: BybitListener, market_aggregator: MarketAggregator) -> None:
    logger.info("🔄 Фоновый синк листингов запущен.")

    while True:
        try:
            await asyncio.sleep(3600)

            all_symbols = await asyncio.to_thread(listener.get_all_usdt_symbols)
            if not all_symbols:
                continue

            new_all_symbols = build_target_symbols(all_symbols)
            current_symbols = set(listener.target_symbols)
            new_symbols = [symbol for symbol in new_all_symbols if symbol not in current_symbols]

            if not new_symbols:
                continue

            await warmup_system(market_aggregator, new_symbols)
            await listener.restart(new_all_symbols)
            logger.info(f"🆕 Обнаружены новые монеты: {', '.join(new_symbols)}. Мониторинг перезапущен.")
        except asyncio.CancelledError:
            logger.info("🛑 Фоновый синк листингов остановлен.")
            raise
        except Exception as e:
            logger.error(f"Ошибка в symbol_sync_worker: {e}", exc_info=True)
