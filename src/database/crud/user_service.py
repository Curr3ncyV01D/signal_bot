import logging
from datetime import timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from src.database.models import User
from src.database.functions import get_utc_now

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
    """Получает пользователей с АКТИВНОЙ подпиской для рассылки алертов."""
    try:
        now = get_utc_now()
        # Пользователь активен, если дата окончания подписки больше текущей
        query = select(User).where(
            and_(
                User.subscription_end.is_not(None),
                User.subscription_end > now
            )
        )
        result = await session.execute(query)
        return list(result.scalars().all())
    except Exception as e:
        logger.error(f"Ошибка при получении активных пользователей: {e}")
        return []

async def activate_trial(session: AsyncSession, user_id: int) -> tuple[bool, str]:
    """Активирует пробный период на 24 часа. Возвращает (успех, сообщение)."""
    try:
        user = await session.get(User, user_id)
        if not user:
            return False, "Пользователь не найден. Нажмите /start."
            
        if user.is_trial_used:
            return False, "❌ Вы уже использовали пробный период."
            
        now = get_utc_now()
        
        # Если вдруг есть текущая активная подписка (например, купил, а потом нажал триал) - плюсуем к ней.
        # Иначе отсчитываем 24 часа от текущего момента.
        if user.subscription_end and user.subscription_end > now:
            user.subscription_end = user.subscription_end + timedelta(hours=24)
        else:
            user.subscription_end = now + timedelta(hours=24)
            
        user.is_trial_used = True
        await session.commit()
        return True, "✅ Пробный период на 24 часа успешно активирован!"
    except Exception as e:
        await session.rollback()
        logger.error(f"Ошибка при активации триала для {user_id}: {e}")
        return False, "Произошла ошибка при активации. Попробуйте позже."

async def get_expired_users(session: AsyncSession) -> list[User]:
    """Получает пользователей, у которых закончилась подписка (для Вышибалы)."""
    try:
        now = get_utc_now()
        query = select(User).where(
            and_(
                User.subscription_end.is_not(None),
                User.subscription_end < now
            )
        )
        result = await session.execute(query)
        return list(result.scalars().all())
    except Exception as e:
        logger.error(f"Ошибка при поиске просроченных подписок: {e}")
        return []

async def clear_expired_subscription(session: AsyncSession, user_id: int) -> None:
    """Обнуляет дату подписки (None) после исключения пользователя."""
    try:
        user = await session.get(User, user_id)
        if user:
            user.subscription_end = None
            await session.commit()
    except Exception as e:
        await session.rollback()
        logger.error(f"Ошибка при обнулении подписки {user_id}: {e}")