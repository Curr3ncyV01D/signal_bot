import asyncio
import logging
import time
from datetime import datetime

logger = logging.getLogger(__name__)


def format_datetime(dt: datetime | None) -> str:
    """Унифицирует форматирование даты и времени для всего бота."""
    if not dt:
        return "Н/Д"
    return f"{dt.strftime('%d.%m.%Y %H:%M')} UTC"

def mask_proxy_url(url: str | None) -> str | None:
    """Маскирует пароль в URL прокси для безопасного логирования."""
    if not url:
        return url
    import re
    return re.sub(r'(?<=://)[^:]+:[^@]+@', '***:***@', url)

async def lag_detector() -> None:
    """Детектор блокировки Event Loop."""
    logger.info("🕵️ Детектор лагов запущен.")

    while True:
        start_time = time.time()
        await asyncio.sleep(1)
        delay = time.time() - start_time - 1

        if delay > 1.5:
            logger.error(
                f"🚨 Критическая блокировка Event Loop. "
                f"Фактическая задержка составила {delay:.3f} сек."
            )
        elif delay > 0.5:
            logger.warning(f"⚠️ ВНИМАНИЕ! Event Loop заблокирован. Задержка: {delay:.3f} сек.")
