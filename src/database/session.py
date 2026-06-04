from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from src.core.config import config

engine = create_async_engine(
    config.DB_URL, 
    echo=False,
    pool_size=20,          # Базовый размер пула
    max_overflow=10,       # Макс. кол-во доп. соединений сверх pool_size
    pool_timeout=30,       # Таймаут ожидания соединения из пула
    pool_recycle=1800      # Пересоздавать соединение каждые 30 мин (защита от разрыва со стороны БД)
)

async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db():
    async with async_session() as session:
        yield session