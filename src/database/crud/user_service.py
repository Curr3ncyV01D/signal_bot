import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.database.models import User

logger = logging.getLogger(__name__)

async def get_or_create_user(session: AsyncSession, user_id: int, username: str | None) -> User | None:
    """Регистрация или получение пользователя."""
    try:
        user = await session.get(User, user_id)
        if user:
            if user.username != username:
                user.username = username
                await session.commit()
            return user

        new_user = User(id=user_id, username=username)
        session.add(new_user)
        await session.commit()
        return new_user
    except Exception as e:
        await session.rollback()
        logger.error(f"Ошибка в get_or_create_user: {e}")
        return await session.get(User, user_id)

async def get_active_users(session: AsyncSession) -> list[User]:
    """Получает всех пользователей для рассылки."""
    try:
        result = await session.execute(select(User))
        return list(result.scalars().all())
    except Exception as e:
        logger.error(f"Ошибка при получении активных пользователей: {e}")
        return []