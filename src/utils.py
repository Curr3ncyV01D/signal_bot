import asyncio
import logging
import time

logger = logging.getLogger(__name__)


async def lag_detector() -> None:
    """Детектор блокировки Event Loop."""
    logger.info("🕵️ Детектор лагов запущен.")

    while True:
        start_time = time.time()
        await asyncio.sleep(1)
        delay = time.time() - start_time - 1

        if delay > 0.5:
            logger.warning(f"⚠️ ВНИМАНИЕ! Event Loop заблокирован. Задержка: {delay:.3f} сек.")
        elif delay > 2.0:
            logger.error(f"🚨 КРИТИЧЕСКИЙ ЛАГ! Бот 'висел' {delay:.3f} сек. PING может отвалиться!")
