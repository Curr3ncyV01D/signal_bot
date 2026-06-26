import asyncio
import logging
import time
import re
from datetime import datetime

logger = logging.getLogger(__name__)

# Ручной маппинг для случаев, когда тикер не совпадает с ID CoinGecko
MANUAL_MAPPING = {
    "BIT": "bitdao",
    "WLD": "worldcoin-org",
    "PEPE": "pepe",
    "SHIB": "shiba-inu",
    # Добавляйте сюда другие монеты по мере необходимости
}


def normalize_bybit_symbol(raw_symbol: str) -> str:
    """
    Нормализует тикер Bybit для поиска в CoinGecko или использования как ключ.
    """
    # В верхний регистр и убираем USDT
    s = raw_symbol.upper().replace("USDT", "")

    # Убираем префиксы 1000, 1000000 и т.д. в начале строки
    s = re.sub(r'^\d+', '', s)

    return s.lower()


def format_datetime(dt: datetime | None) -> str:
    """Унифицирует форматирование даты и времени для всего бота."""
    if not dt:
        return "Н/Д"
    return f"{dt.strftime('%d.%m.%Y %H:%M')} UTC"


def format_smart_num(val: float | None, is_percent: bool = False, show_sign: bool = False, decimal_places: int = 1) -> str:
    """Форматирует число"""
    if val is None:
        return "Н/Д"
        
    num = float(val)
    rounded = round(num, decimal_places)
    is_integer = rounded.is_integer()

    if is_integer:
        formatted = f"{int(abs(rounded)):,}".replace(",", " ")
    else:
        formatted = f"{abs(rounded):,.{decimal_places}f}".replace(",", " ").replace(".", ",")

    # Добавляем знак
    sign = ""
    if rounded > 0 and show_sign:
        sign = "+"
    elif rounded < 0:
        sign = "-"

    res = f"{sign}{formatted}"
    return f"{res}%" if is_percent else res


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
                tasks_info = f" Активных задач: {len(asyncio.all_tasks())}"
                logger.error(
                    f"🚨 Критическая блокировка Event Loop. "
                    f"Фактическая задержка составила {delay:.3f} сек.{queue_info}.{tasks_info}"
                )
            else:
                logger.warning(f"⚠️ ВНИМАНИЕ! Event Loop заблокирован. Задержка: {delay:.3f} сек.{queue_info}")
