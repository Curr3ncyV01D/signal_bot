import orjson
import logging
import sys
from datetime import datetime
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator

class Settings(BaseSettings):
    # === 0. СИСТЕМНЫЕ МЕТРИКИ (Internal) ===
    START_TIME: datetime | None = None
    # Настройка логгирования
    LOG_LEVEL: str = "INFO"
    DEBUG_LOGGERS: list[str] = ["aiogram", "aiogram.event", "pybit"]
    INFRA_LOGGERS: list[str] = [
        "urllib3",
        "websocket",
        "aiohttp",
        "asyncio",
        "uvicorn",
        "httpcore",
    ]

    # === 1. ОСНОВНЫЕ НАСТРОЙКИ (Infrastructure) ===
    BOT_TOKEN: str
    DB_URL: str
    PRIVATE_CHANNEL_ID: str
    
    # === 2. ПЛАТЕЖНАЯ СИСТЕМА (Billing & CryptoPay) ===
    # Интеграция
    CRYPTOPAY_TOKEN: str
    CRYPTOPAY_TESTNET: bool = False
    
    # Бизнес-правила (Тарифы и деньги)
    # Тарифы подписки (дней: цена_usdt)
    TARIFFS: dict[int, float] = {
        1: 1.0,
        30: 20.0,
        60: 40.0,
        150: 100.0
    }
    REFERRAL_BONUS_PERCENT: float = 15.0

    # === 3. ИНТЕРФЕЙС И UX (UI Logic) ===
    GUIDE_URL: str = "https://google.com"
    TRANSACTION_HISTORY_LIMIT: int = 10          # Количество последних транзакций отображаемых в истории
    MAX_SUB_DAYS: int = 3650                     # Максимальный срок подписки, что может задать админ(в днях)
    CASCADE_UI_DISPLAY_COUNT: int = 5            # С какой строки показывать каскад в тексте
    CASCADE_VOLCANO_MULTIPLIER: float = 2.0      # Множитель для смены эмодзи на вулкан

    # === 4. АНАЛИТИЧЕСКОЕ ЯДРО (Market Logic / Magic Numbers) ===
    # Чувствительность и Анти-спам
    ALERT_GROWTH_PERCENTAGE: float = 1.50        # Прирост +n% для нового алерта
    VOLUME_MULTIPLIER: float = 3.0               # Во сколько раз 1h порог больше 5m
    GLOBAL_COOLDOWN_SEC: int = 180               # Задержка между алертами (сек)
    SQUEEZE_RATIO: float = 0.3                   # Доля 5м объема от 1ч для "QUICK SQUEEZE"

    # Пороги фильтрации
    MIN_LIQ_VALUE_FILTER: float = 100.0          # Отсечение шума ликвидаций ($)
    MIN_TRADE_VALUE_FOR_CVD: float = 300.0       # Мин. сделка для подсчета дельты ($)
    CASCADE_TRIGGER_COUNT: int = 15              # Кол-во событий для алерта "КАСКАД"

    # Временные окна (в секундах)
    WINDOW_VOLUME_1H: int = 3600                 
    WINDOW_SQUEEZE_5M: int = 300                 
    WINDOW_CASCADE: int = 150                    

    # Технические индикаторы
    RSI_PERIOD: int = 14                         
    RSI_KLINE_INTERVAL: str = "60"               
    OI_WINDOW_MINUTES: int = 5                   

    # === 5. МОНИТОРИНГ И ПОДКЛЮЧЕНИЯ (Networking) ===
    # Фильтрация монет
    IGNORED_SYMBOLS: list[str] = [] 

    @field_validator("IGNORED_SYMBOLS", mode="before")
    @classmethod
    def parse_ignored_symbols(cls, value):
        if isinstance(value, str):
            try:
                data = orjson.loads(value)
            except orjson.JSONDecodeError:
                data = [s.strip() for s in value.split(",")]
            return [s.upper() for s in data if s.strip()]
        return value

    # Сетевые параметры
    PROXY_URL: str | None = None 
    WS_CHUNK_SIZE: int = 25                      
    WS_DELAY_PROD: float = 1.5                   
    WS_DELAY_DEV: float = 0.8                    

    # Режим разработки
    DEV_MODE: bool = False
    DEV_SYMBOL_LIMIT: int = 200

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


def setup_logging() -> None:
    # 1. Получаем уровень из конфига
    level_name = config.LOG_LEVEL.upper()
    level = getattr(logging, level_name, logging.INFO)

    # 2. Настраиваем корневой логгер
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # 3. Создаем обработчик для консоли ПРАВИЛЬНО
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s - [%(levelname)s] - %(name)s - %(message)s"
    ))
    # ВАЖНО: Ставим обработчику уровень NOTSET, чтобы он пропускал всё,
    # что разрешит сам логгер
    handler.setLevel(logging.NOTSET) 
    
    root_logger.handlers = [] # Очищаем старые обработчики
    root_logger.addHandler(handler)

    # 4. Глушим инфраструктуру (только ошибки)
    SILENT_LOGGERS = ["pybit", "websocket", "aiohttp", "asyncio", "urllib3", "httpcore"]
    for logger_name in SILENT_LOGGERS:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    # 5. Настраиваем aiogram.event в зависимости от стартового уровня
    if level == logging.DEBUG:
        logging.getLogger("aiogram.event").setLevel(logging.INFO)
    else:
        logging.getLogger("aiogram.event").setLevel(logging.WARNING)

config = Settings()
