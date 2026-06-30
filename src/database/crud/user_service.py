import logging
from datetime import timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, or_
from sqlalchemy.exc import SQLAlchemyError
from src.database.models import User
from src.database.functions import get_utc_now

logger = logging.getLogger(__name__)

# Кеш активных пользователей для рассылки (обновляется раз в минуту)
_active_users_cache = []
_last_cache_update = None

async def get_or_create_user(
    session: AsyncSession, 
    user_id: int, 
    username: str | None, 
    referrer_id: int | None = None
) -> User | None:
    """Регистрация или получение пользователя с поддержкой реферальной системы."""
    try:
        user = await session.get(User, user_id)
        if user:
            if user.username != username:
                user.username = username
                await session.commit()
            return user

        # Проверка реферера: не сам себя и реферер должен существовать
        valid_referrer_id = None
        if referrer_id and referrer_id != user_id:
            referrer = await session.get(User, referrer_id)
            if referrer:
                valid_referrer_id = referrer_id

        new_user = User(
            id=user_id, 
            username=username, 
            referrer_id=valid_referrer_id
        )
        session.add(new_user)
        await session.commit()
        return new_user
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"Ошибка БД в get_or_create_user: {e}")
        return await session.get(User, user_id)
    except Exception as e:
        await session.rollback()
        logger.error(f"Непредвиденная ошибка в get_or_create_user: {e}")
        return await session.get(User, user_id)

async def get_active_users(session: AsyncSession) -> list[User]:
    """Получает пользователей с АКТИВНОЙ подпиской для рассылки алертов (с кешированием)."""
    global _active_users_cache, _last_cache_update
    
    now = get_utc_now()
    
    # Если кеш свежий (меньше 60 секунд) — отдаем его
    if _last_cache_update and (now - _last_cache_update).total_seconds() < 60:
        return _active_users_cache

    try:
        query = select(User).where(
            and_(
                User.subscription_end.is_not(None),
                User.subscription_end > now,
                User.is_blocked == False
            )
        )
        result = await session.execute(query)
        users = list(result.scalars().all())
        
        # Обновляем кеш
        _active_users_cache = users
        _last_cache_update = now
        
        return users
    except SQLAlchemyError as e:
        logger.error(f"Ошибка БД при получении активных пользователей: {e}")
        return _active_users_cache
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при получении активных пользователей: {e}")
        return _active_users_cache # Возвращаем старый кеш при ошибке БД

async def activate_trial(session: AsyncSession, user_id: int) -> tuple[bool, str]:
    """Помечает пробный период как использованный. Начисление срока делает billing_service."""
    try:
        user = await session.get(User, user_id, with_for_update=True)
        if not user:
            return False, "Пользователь не найден. Нажмите /start."
            
        if user.is_trial_used:
            return False, "Пробный период уже был использован."

        user.is_trial_used = True
        return True, "✅ Пробный период на 24 часа успешно активирован!"
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"Ошибка БД при активации триала для {user_id}: {e}")
        return False, "Произошла ошибка при активации. Попробуйте позже."
    except Exception as e:
        await session.rollback()
        logger.error(f"Непредвиденная ошибка при активации триала для {user_id}: {e}")
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
    except SQLAlchemyError as e:
        logger.error(f"Ошибка БД при поиске просроченных подписок: {e}")
        return []
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при поиске просроченных подписок: {e}")
        return []

async def clear_expired_subscription(session: AsyncSession, user_id: int) -> None:
    """Обнуляет дату подписки (None) после исключения пользователя."""
    try:
        user = await session.get(User, user_id)
        if user:
            user.subscription_end = None
            await session.commit()
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"Ошибка БД при обнулении подписки {user_id}: {e}")
    except Exception as e:
        await session.rollback()
        logger.error(f"Непредвиденная ошибка при обнулении подписки {user_id}: {e}")

async def get_users_count(session: AsyncSession) -> int:
    """Возвращает общее количество пользователей в БД (для расчета страниц)."""
    try:
        query = select(func.count(User.id))
        result = await session.execute(query)
        return result.scalar() or 0
    except SQLAlchemyError as e:
        logger.error(f"Ошибка БД при подсчете пользователей: {e}")
        return 0
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при подсчете пользователей: {e}")
        return 0

async def get_users_page(session: AsyncSession, limit: int = 10, offset: int = 0) -> list[User]:
    """Получает страницу пользователей с сортировкой от новых к старым."""
    try:
        query = select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
        result = await session.execute(query)
        return list(result.scalars().all())
    except SQLAlchemyError as e:
        logger.error(f"Ошибка БД при получении страницы пользователей: {e}")
        return []
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при получении страницы пользователей: {e}")
        return []

async def toggle_user_block(session: AsyncSession, user_id: int) -> bool | None:
    """Инвертирует статус блокировки."""
    try:
        user = await session.get(User, user_id)
        if not user:
            return None
        
        user.is_blocked = not user.is_blocked
        await session.commit()
        return user.is_blocked
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"Ошибка БД при смене статуса блокировки для {user_id}: {e}")
        return None
    except Exception as e:
        await session.rollback()
        logger.error(f"Непредвиденная ошибка при смене статуса блокировки для {user_id}: {e}")
        return None

async def update_user_subscription(session: AsyncSession, user_id: int, days: int) -> User | None:
    """
    Обновляет срок подписки пользователя.
    Если days > 0: устанавливает subscription_end = get_utc_now() + days.
    Если days == 0: аннулирует подписку (subscription_end = None).
    """
    try:
        user = await session.get(User, user_id)
        if not user:
            return None
        
        if days > 0:
            user.subscription_end = get_utc_now() + timedelta(days=days)
        else:
            user.subscription_end = None
            
        await session.commit()
        return user
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"Ошибка БД при обновлении подписки для {user_id}: {e}")
        return None
    except Exception as e:
        await session.rollback()
        logger.error(f"Непредвиденная ошибка при обновлении подписки для {user_id}: {e}")
        return None

async def update_user_settings(session: AsyncSession, user_id: int, **kwargs) -> User | None:
    """
    Универсальный метод для обновления любых полей настроек пользователя.
    """
    try:
        user = await session.get(User, user_id)
        if not user:
            return None

        for key, value in kwargs.items():
            if hasattr(user, key):
                setattr(user, key, value)
        
        await session.commit()
        await session.refresh(user)
        return user
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"Ошибка БД при обновлении настроек пользователя {user_id}: {e}")
        return None
    except Exception as e:
        await session.rollback()
        logger.error(f"Непредвиденная ошибка при обновлении настроек пользователя {user_id}: {e}")
        return None

async def get_all_receiver_ids(session: AsyncSession) -> list[int]:
    """Возвращает список ID всех пользователей, которые не заблокированы ботом."""
    try:
        query = select(User.id).where(User.is_blocked == False)
        result = await session.execute(query)
        return list(result.scalars().all())
    except Exception as e:
        logger.error(f"Ошибка при получении всех ID получателей: {e}")
        return []

async def get_vip_receiver_ids(session: AsyncSession) -> list[int]:
    """Возвращает список ID пользователей с активной подпиской."""
    try:
        now = get_utc_now()
        query = select(User.id).where(
            and_(
                User.subscription_end.is_not(None),
                User.subscription_end > now,
                User.is_blocked == False
            )
        )
        result = await session.execute(query)
        return list(result.scalars().all())
    except Exception as e:
        logger.error(f"Ошибка при получении VIP ID получателей: {e}")
        return []

async def get_free_receiver_ids(session: AsyncSession) -> list[int]:
    """Возвращает список ID пользователей без активной подписки."""
    try:
        now = get_utc_now()
        query = select(User.id).where(
            and_(
                User.is_blocked == False,
                or_(
                    User.subscription_end.is_(None),
                    User.subscription_end <= now
                )
            )
        )
        result = await session.execute(query)
        return list(result.scalars().all())
    except Exception as e:
        logger.error(f"Ошибка при получении Free ID получателей: {e}")
        return []

async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    """Получает пользователя по его ID."""
    try:
        return await session.get(User, user_id)
    except SQLAlchemyError as e:
        logger.error(f"Ошибка БД при получении пользователя {user_id}: {e}")
        return None
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при получении пользователя {user_id}: {e}")
        return None
