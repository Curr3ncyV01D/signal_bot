import os
import orjson
import logging
import sys
from pathlib import Path
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
    REDIS_URL: str = "redis://:pass@redis:6379/0"
    REDIS_RAW_STREAM_NAME: str = "csl:signals:raw"
    REDIS_READY_STREAM_NAME: str = "csl:signals:ready"
    REDIS_STREAM_MAXLEN: int = 1000
    REDIS_ARTIST_CONSUMER_GROUP: str = "csl:artist_group"
    REDIS_MESSENGER_CONSUMER_GROUP: str = "csl:messenger_group"
    REDIS_CACHE_INVALIDATION_CHANNEL: str = "csl:cache_invalidation"
    REDIS_CHART_CACHE_PREFIX: str = "csl:chart_cache"
    REDIS_PENDING_IDLE_MS: int = 30000
    PRIVATE_CHANNEL_ID: str | None = None
    LOG_CHANNEL_ID: str | None = None
    NEWS_CHANNEL_ID: str | None = None
    NEWS_CHANNEL_URL: str | None = None
    
    # === 2. ПЛАТЕЖНАЯ СИСТЕМА (Billing & CryptoPay) ===
    # Интеграция
    CRYPTOPAY_TOKEN: str
    CRYPTOPAY_TESTNET: bool = False
    
    # Бизнес-правила (Тарифы и деньги)
    # Тарифы подписки (дней: цена_usdt)
    TARIFFS: dict[int, float] = {
        30: 25.0
    }
    SUB_MONTHLY_PRICE: float = TARIFFS[30]
    TRIAL_DURATION_DAYS: int = 1
    REFERRAL_BONUS_PERCENT: float = 15.0

    # === 3. ИНТЕРФЕЙС И UX (UI Logic) ===
    GUIDE_URL: str = "https://google.com"
    SUPPORT_URL: str = "https://t.me/Helper_CSL"
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
    MIN_OI_CHANGE_PCT: float = 1.0
    MIN_TRADE_VALUE_FOR_CVD: float = 300.0       # Мин. сделка для подсчета дельты ($)
    CASCADE_TRIGGER_COUNT: int = 15              # Кол-во событий для алерта "КАСКАД"

    # Временные окна (в секундах)
    WINDOW_VOLUME_1H: int = 3600                 
    WINDOW_SQUEEZE_5M: int = 300                 
    WINDOW_CASCADE: int = 150                    

    # Технические индикаторы
    RSI_PERIOD: int = 14                         # Период расчета RSI (кол-во баров)
    RSI_KLINE_INTERVAL: str = "60"               # Таймфрейм свечей для RSI (в минутах)
    OI_WINDOW_MINUTES: int = 5                   # Окно анализа изменения ОИ (минуты)
    TICKER_THROTTLE_SEC: float = 2.0             # Лимит частоты обновления цен (сек) для разгрузки CPU
    CHART_CACHE_TTL_SEC: int = 180               # Время жизни кэша готового графика (сек)
    CHART_PRICE_DELTA_THRESHOLD: float = 0.005   # Порог изменения цены (0.5%) для перерисовки графика
    CHART_MIN_VOLUME_USD: float = 5000.0         # Мин. USD объем ликвидации для рендера графика
    CHART_MIN_CAP_RATIO: float = 0.01            # Мин. % от капитализации для рендера графика
    CHART_MIN_VOL_RATIO: float = 1.0             # Мин. % от суточного объема для рендера графика
    CHART_RSI_EXTREME_UPPER: float = 80.0
    CHART_RSI_EXTREME_LOWER: float = 20.0
    CHART_ALWAYS_RENDER_TYPES: list[str] = ["CASCADE", "SQUEEZE"] # Алерты с обязательной отрисовкой
    CHART_BUCKET_CAPACITY: float = 40.0          # Макс. запас рендеров графиков
    CHART_BUCKET_REFILL_RATE: float = 0.36       # Скорость пополнения токенов в секунду
    CHART_SIGNAL_MAX_AGE_SEC: int = 20           # Макс. возраст сигнала для рендера
    CHART_PRIORITY_THRESHOLD: float = 15.0       # Ниже этого уровня рендерим только приоритетные
    CHART_CRITICAL_THRESHOLD: float = 5.0        # Ниже этого уровня рендерим только каскады
    CHART_PRIORITY_VOLUME_USD: float = 10000.0   # Порог USD объема для приоритетного рендера

    # === 5. МОНИТОРИНГ И ПОДКЛЮЧЕНИЯ (Networking) ===
    # Фильтрация монет
    IGNORED_SYMBOLS: list[str] = [] 

    @field_validator("PRIVATE_CHANNEL_ID", "LOG_CHANNEL_ID", "NEWS_CHANNEL_ID", mode="before")
    @classmethod
    def parse_optional_channel_ids(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return str(value)

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

    @field_validator("CHART_ALWAYS_RENDER_TYPES", mode="before")
    @classmethod
    def parse_chart_always_render_types(cls, value):
        if isinstance(value, str):
            try:
                data = orjson.loads(value)
            except orjson.JSONDecodeError:
                data = [item.strip() for item in value.split(",")]
            return [str(item).strip().upper() for item in data if str(item).strip()]
        return value

    @property
    def is_channel_mode_enabled(self) -> bool:
        return (
            self.PRIVATE_CHANNEL_ID is not None
            and self.NEWS_CHANNEL_ID is not None
        )

    # Сетевые параметры
    PROXY_URL: str | None = None 
    WS_CHUNK_SIZE: int = 25                      
    WS_DELAY_PROD: float = 1.5                   
    WS_DELAY_DEV: float = 0.8                    

    # Режим разработки
    DEV_MODE: bool = False
    DEV_SYMBOL_LIMIT: int = 20

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

config = Settings()


BASE_DIR = Path(__file__).resolve().parent.parent.parent
ASSETS_DIR = BASE_DIR / "assets" / "images"


class ImagePaths:
    WELCOME = str(ASSETS_DIR / "1_welcome.png")
    PAYMENT = str(ASSETS_DIR / "2_payment.png")
    SETTINGS = str(ASSETS_DIR / "3_settings.png")
    WALLET = str(ASSETS_DIR / "4_wallet.png")
    AFFILIATE = str(ASSETS_DIR / "5_affiliate.png")
    PLACEHOLDER = str(ASSETS_DIR / "placeholder.png")


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
