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


def format_smart_num(val: float, is_percent: bool = False) -> str:
    """Форматирует число по-человечески: пробелы в тысячах и до 1 знака после запятой."""
    num = float(val)
    rounded = round(num, 1)
    is_integer = rounded.is_integer()

    if is_integer:
        formatted = f"{int(rounded):,}".replace(",", " ")
    else:
        formatted = f"{rounded:,.1f}".replace(",", " ").replace(".", ",")

    return f"{formatted}%" if is_percent else formatted


def parse_numeric_input(text: str) -> float:
    """Парсит числовой ввод с пробелами, запятыми и лишними точками."""
    normalized = text.strip().replace(" ", "").replace(",", ".")
    if not normalized:
        raise ValueError("empty input")

    sign = ""
    if normalized[0] in "+-":
        sign = normalized[0]
        normalized = normalized[1:]

    digits: list[str] = []
    last_dot_index = normalized.rfind(".")
    for idx, char in enumerate(normalized):
        if char.isdigit():
            digits.append(char)
        elif char == "." and idx == last_dot_index:
            digits.append(char)

    cleaned = "".join(digits).strip(".")
    if not cleaned:
        raise ValueError("invalid numeric input")

    return float(f"{sign}{cleaned}")

def mask_proxy_url(url: str | None) -> str | None:
    """Маскирует пароль в URL прокси для безопасного логирования."""
    if not url:
        return url
    import re
    return re.sub(r'(?<=://)[^:]+:[^@]+@', '***:***@', url)

async def lag_detector(queue: asyncio.Queue | None = None) -> None:
    """Детектор блокировки Event Loop.
    Если передана очередь, выводит её размер при лагах.
    """
    logger.info("🕵️ Детектор лагов запущен.")

    while True:
        start_time = time.time()
        await asyncio.sleep(1)
        delay = time.time() - start_time - 1

        if delay > 1.0:
            queue_info = f" Задач в очереди: {queue.qsize()}" if queue else ""
            if delay > 1.5:
                logger.error(
                    f"🚨 Критическая блокировка Event Loop. "
                    f"Фактическая задержка составила {delay:.3f} сек.{queue_info}"
                )
            else:
                logger.warning(f"⚠️ ВНИМАНИЕ! Event Loop заблокирован. Задержка: {delay:.3f} сек.{queue_info}")
