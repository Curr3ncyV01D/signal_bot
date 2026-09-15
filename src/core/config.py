import os
import orjson
import logging
import sys
from pathlib import Path
from datetime import datetime
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator, model_validator

from src.core.dto import SettingPresetDTO, TariffDTO

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
    REDIS_PASSWORD: str
    REDIS_PORT: int = 6379
    REDIS_URL: str | None = None
    REDIS_RAW_STREAM_NAME: str = "csl:signals:raw"
    REDIS_READY_STREAM_NAME: str = "csl:signals:ready"
    REDIS_STREAM_MAXLEN: int = 1000
    REDIS_ARTIST_CONSUMER_GROUP: str = "csl:artist_group"
    REDIS_MESSENGER_CONSUMER_GROUP: str = "csl:messenger_group"
    REDIS_CACHE_INVALIDATION_CHANNEL: str = "csl:cache_invalidation"
    REDIS_CHART_CACHE_PREFIX: str = "csl:chart_cache"
    REDIS_PENDING_IDLE_MS: int = 30000
    LOG_CHANNEL_ID: str | None = None
    NEWS_CHANNEL_ID: int | str | None = None
    NEWS_CHANNEL_URL: str | None = None
    
    # === 2. ПЛАТЕЖНАЯ СИСТЕМА (Billing & CryptoPay / Cryptomus) ===
    # Интеграция
    CRYPTOPAY_TOKEN: str | None = None
    CRYPTOPAY_TESTNET: bool = False
    CRYPTOMUS_MERCHANT_ID: str | None = None
    CRYPTOMUS_PAYMENT_API_KEY: str | None = None
    CRYPTOMUS_API_BASE_URL: str = "https://api.cryptomus.com/v1"
    CRYPTOMUS_CREATE_PAYMENT_PATH: str = "/payment"
    CRYPTOMUS_PAYMENT_INFO_PATH: str = "/payment/info"
    CRYPTOMUS_REQUEST_TIMEOUT_SEC: int = 15
    CRYPTOMUS_INVOICE_LIFETIME_SEC: int = 7200
    CRYPTOMUS_ACCURACY_PAYMENT_PERCENT: float = 0.0
    PAYMENT_TOLERANCE_USD: float = 0.5
    PAYMENT_MANUAL_WALLET: str | None = None
    ADMIN_PAYMENT_CHAT_ID: int | None = None

    # CactusPay (H2H: Карты РФ / СБП)
    CACTUS_MERCHANT_ID: str | None = None
    CACTUS_SECRET_KEY: str | None = None
    CACTUS_API_URL: str = "https://lk.cactuspay.pro/api"
    CACTUS_INVOICE_LIFETIME_SEC: int = 480
    CACTUS_H2H_METHOD: str = "card"
    CACTUS_REQUEST_TIMEOUT_SEC: int = 15
    
    # Бизнес-правила (Тарифы и деньги)
    # Тарифы подписки (дней: TariffDTO с ценами в USD и RUB)
    TARIFFS: dict[int, TariffDTO] = Field(
        default_factory=lambda: {
            7: TariffDTO(days=7, price_usd=7.5, price_rub=1000.0),
            30: TariffDTO(days=30, price_usd=12.5, price_rub=1500.0, data_extra="🏷️ -50%"),
        }
    )
    SUB_MONTHLY_PRICE: float = Field(default_factory=lambda: 25.0)
    TRIAL_DURATION_DAYS: int = 1
    COMMUNITY_BONUS_HOURS: int = 48
    REFERRAL_BONUS_PERCENT: float = 15.0
    FREE_TRIAL_TOTAL_DAYS: int = 3
    SETTING_PRESETS: dict[str, SettingPresetDTO] = Field(
        default_factory=lambda: {
            "SCALPER": SettingPresetDTO(
                threshold=8000.0,
                threshold_cascade=5000.0,
                threshold_mode="PERCENT",
                threshold_oi_percent=5.0,
                threshold_oi_value=100000.0,
                threshold_mcap_pct=0.005,
                threshold_mcap_usd_min=1000.0,
                threshold_cascade_mcap_pct=0.008,
                threshold_cascade_mcap_usd_min=1000.0,
                filter_rsi_min=35.0,
                filter_rsi_max=65.0,
                alert_cascade=True,
                alert_volume=True,
                alert_squeeze=True,
                alert_longs=True,
                alert_shorts=True,
                alert_oi=True,
                alert_rsi=True,
                alert_cvd=True,
            ),
            "BALANCED": SettingPresetDTO(
                threshold=20000.0,
                threshold_cascade=15000.0,
                threshold_mode="PERCENT",
                threshold_oi_percent=15.0,
                threshold_oi_value=300000.0,
                threshold_mcap_pct=0.01,
                threshold_mcap_usd_min=5000.0,
                threshold_cascade_mcap_pct=0.015,
                threshold_cascade_mcap_usd_min=5000.0,
                filter_rsi_min=30.0,
                filter_rsi_max=70.0,
                alert_cascade=True,
                alert_volume=True,
                alert_squeeze=True,
                alert_longs=True,
                alert_shorts=True,
                alert_oi=True,
                alert_rsi=True,
                alert_cvd=True,
            ),
            "CONSERVATIVE": SettingPresetDTO(
                threshold=100000.0,
                threshold_cascade=80000.0,
                threshold_mode="USD",
                threshold_oi_percent=20.0,
                threshold_oi_value=500000.0,
                threshold_mcap_pct=0.05,
                threshold_mcap_usd_min=20000.0,
                threshold_cascade_mcap_pct=0.1,
                threshold_cascade_mcap_usd_min=20000.0,
                filter_rsi_min=20.0,
                filter_rsi_max=80.0,
                alert_cascade=True,
                alert_volume=True,
                alert_squeeze=True,
                alert_longs=True,
                alert_shorts=True,
                alert_oi=True,
                alert_rsi=True,
                alert_cvd=True,
            ),
            "FREE_NOISE": SettingPresetDTO(
                threshold_mode="USD",
                threshold=2000.0,
                threshold_cascade=1500.0,
                threshold_oi_percent=3.0,
                threshold_oi_value=50000.0,
                threshold_mcap_pct=0.005,
                threshold_mcap_usd_min=1000.0,
                threshold_cascade_mcap_pct=0.005,
                threshold_cascade_mcap_usd_min=1000.0,
                filter_rsi_min=40.0,
                filter_rsi_max=60.0,
                alert_cascade=True,
                alert_volume=True,
                alert_squeeze=True,
                alert_longs=True,
                alert_shorts=True,
                alert_oi=True,
                alert_rsi=True,
                alert_cvd=False,
            ),
        }
    )

    # === 3. ИНТЕРФЕЙС И UX (UI Logic) ===
    GUIDE_URL: str = "https://google.com"
    SUPPORT_URL: str = "https://t.me/Helper_CSL"
    COMMUNITY_GROUP_ID: int | None = None
    COMMUNITY_GROUP_LINK: str | None = None
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
    GATE_CACHE_TTL_SEC: int = 600                # TTL кэша проверки членства в каналах (10 минут)
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

    @field_validator("LOG_CHANNEL_ID", mode="before")
    @classmethod
    def parse_optional_log_channel_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return str(value)

    @field_validator("NEWS_CHANNEL_ID", mode="before")
    @classmethod
    def parse_optional_news_channel_id(cls, value: int | str | None) -> int | str | None:
        if value is None:
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            normalized = value.strip()
            if not normalized:
                return None
            try:
                return int(normalized)
            except ValueError:
                return normalized
        return value

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

    @model_validator(mode="after")
    def build_redis_url(self):
        if self.REDIS_URL:
            self.REDIS_URL = self.REDIS_URL.strip()
            return self
        self.REDIS_URL = f"redis://:{self.REDIS_PASSWORD}@redis:{self.REDIS_PORT}/0"
        return self

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
SETTING_PRESETS: dict[str, SettingPresetDTO] = config.SETTING_PRESETS
TARIFFS: dict[int, TariffDTO] = config.TARIFFS


BASE_DIR = Path(__file__).resolve().parent.parent.parent
ASSETS_DIR = BASE_DIR / "assets" / "images"


class ImagePaths:
    WELCOME = str(ASSETS_DIR / "1_welcome.png")
    PAYMENT = str(ASSETS_DIR / "2_payment.png")
    SETTINGS = str(ASSETS_DIR / "3_settings.png")
    WALLET = str(ASSETS_DIR / "4_wallet.png")
    AFFILIATE = str(ASSETS_DIR / "5_affiliate.png")
    PLACEHOLDER = str(ASSETS_DIR / "placeholder.png")
    PAYMENT_QR = str(ASSETS_DIR / "payment_qr.jpg")


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
