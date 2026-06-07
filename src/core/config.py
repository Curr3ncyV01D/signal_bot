import json
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator

class Settings(BaseSettings):
    # Базовые настройки (Обязательные)
    BOT_TOKEN: str
    PRIVATE_CHANNEL_ID: str
    DB_URL: str
    GUIDE_URL: str = "https://google.com"

    # Список игнорируемых монет (например, ["BTCUSDT", "ETHUSDT"])
    # Если в .env ничего не указано, список будет пустым
    IGNORED_SYMBOLS: list[str] = [] 

    @field_validator("IGNORED_SYMBOLS", mode="before")
    @classmethod
    def parse_ignored_symbols(cls, value):
        if isinstance(value, str):
            try:
                # Пытаемся распарсить как JSON: ["BTCUSDT"]
                data = json.loads(value)
            except json.JSONDecodeError:
                # Если не JSON, парсим как строку через запятую: BTCUSDT,ETHUSDT
                data = [s.strip() for s in value.split(",")]
            # Сразу переводим в верхний регистр для надежности
            return [s.upper() for s in data if s.strip()]
        return value

    # Прокси-адрес (необязателен и нужен только для разработки. Пример, http://127.0.0.1:7890)
    # Если в .env ничего не указано, будет None
    PROXY_URL: str | None = None 

    # Режим разработчика
    DEV_MODE: bool = False
    DEV_SYMBOL_LIMIT: int = 220

    # --- БИЗНЕС-ЛОГИКА (Магические числа) ---
    
    # 1. Настройки чувствительности алертов
    ALERT_GROWTH_PERCENTAGE: float = 1.50        # Прирост +n% для нового алерта
    VOLUME_MULTIPLIER: float = 3.0               # Во сколько раз 1h порог больше 5m порога
    GLOBAL_COOLDOWN_SEC: int = 180               # Задержка между алертами (сек)

    # 2. Настройки Каскадов
    CASCADE_TRIGGER_COUNT: int = 15              # Кол-во событий для алерта "LIQ CASCADE"
    CASCADE_UI_DISPLAY_COUNT: int = 5            # Кол-во событий для показа строки в сообщении
    CASCADE_VOLCANO_MULTIPLIER: float = 2.0      # Множитель для эмоджи при больших каскадах

    # 3. Настройки UI и Фильтров
    SQUEEZE_RATIO: float = 0.3                   # Доля 5м объема от 1ч объема для "QUICK SQUEEZE"
    MIN_LIQ_VALUE_FILTER: float = 100.0          # Отсечение рыночного шума (в долларах)
    MIN_TRADE_VALUE_FOR_CVD: float = 200.0       # Порог сделки для подсчета Кумулитвной Дельты

    # 4. Временные окна для расчетов (в секундах)
    WINDOW_VOLUME_1H: int = 3600                 # Окно для LIQ VOLUME
    WINDOW_SQUEEZE_5M: int = 300                 # Окно для QUICK SQUEEZE
    WINDOW_CASCADE: int = 150                    # Окно для счета событий каскада

    # 5. Настройки аналитики
    RSI_PERIOD: int = 14                         #
    RSI_KLINE_INTERVAL: str = "60"               # Интервал свечей в минутах
    OI_WINDOW_MINUTES: int = 5                   # Окно анализа Открытого Интереса в минутах
    
    # --- ПОДКЛЮЧЕНИЕ ---
    WS_CHUNK_SIZE: int = 25                      # Кол-во монет на одно WebSocket соединение
    WS_DELAY_PROD: float = 1.5                   # Задержка между запросами в Bybit
    WS_DELAY_DEV: float = 0.8                    # Задержка между запросами в Bybit в режиме разработке

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

config = Settings()