from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from src.core.config import config

engine = create_async_engine(config.DB_URL, echo=False)

async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db():
    async with async_session() as session:
        yield session