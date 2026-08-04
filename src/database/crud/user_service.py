import logging
from datetime import timedelta
from sqlalchemy import String, and_, cast, func, or_, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import config
from src.core.localization import resolve_initial_locale
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
    referrer_id: int | None = None,
    telegram_language_code: str | None = None,
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
            referrer_id=valid_referrer_id,
            language_code=resolve_initial_locale(telegram_language_code),
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


async def complete_user_setup(session: AsyncSession, user_id: int) -> User | None:
    """Помечает онбординг пользователя завершенным."""
    try:
        user = await session.get(User, user_id)
        if not user:
            return None

        user.is_setup_completed = True
        user.onboarding_step = "COMPLETED"
        await session.commit()
        await session.refresh(user)
        return user
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"Ошибка БД при завершении онбординга для {user_id}: {e}")
        return None
    except Exception as e:
        await session.rollback()
        logger.error(f"Непредвиденная ошибка при завершении онбординга для {user_id}: {e}")
        return None

async def get_active_users(session: AsyncSession, force_refresh: bool = False) -> list[User]:
    """Получает пользователей с АКТИВНОЙ подпиской для рассылки алертов (с кешированием)."""
    global _active_users_cache, _last_cache_update
    
    now = get_utc_now()
    
    # Если кеш свежий (меньше 60 секунд) — отдаем его
    if not force_refresh and _last_cache_update and (now - _last_cache_update).total_seconds() < 60:
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
        return True, "✅ Пробный период успешно активирован!"
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

async def get_users_filtered(
    session: AsyncSession,
    page: int,
    limit: int,
    status_filter: str = "all",
    search_query: str | None = None,
) -> tuple[list[User], int]:
    """Возвращает отфильтрованную страницу пользователей и общее количество записей."""
    try:
        normalized_page = max(page, 1)
        normalized_limit = max(limit, 1)
        now = get_utc_now()
        conditions = []

        if status_filter == "active":
            conditions.extend(
                [
                    User.subscription_end.is_not(None),
                    User.subscription_end > now,
                ]
            )
        elif status_filter == "inactive":
            conditions.append(
                or_(
                    User.subscription_end.is_(None),
                    User.subscription_end <= now,
                )
            )

        normalized_search = search_query.strip() if search_query else ""
        if normalized_search:
            search_conditions = [
                User.username.ilike(f"%{normalized_search}%"),
                cast(User.id, String).like(f"%{normalized_search}%"),
            ]

            if normalized_search.isdigit():
                search_conditions.insert(0, User.id == int(normalized_search))

            conditions.append(or_(*search_conditions))

        users_query = select(User)
        count_query = select(func.count(User.id))

        if conditions:
            filter_clause = and_(*conditions)
            users_query = users_query.where(filter_clause)
            count_query = count_query.where(filter_clause)

        users_query = users_query.order_by(User.created_at.desc()).limit(normalized_limit).offset(
            (normalized_page - 1) * normalized_limit
        )

        users_result = await session.execute(users_query)
        total_count_result = await session.execute(count_query)

        return list(users_result.scalars().all()), total_count_result.scalar() or 0
    except SQLAlchemyError as e:
        logger.error(f"Ошибка БД при получении отфильтрованных пользователей: {e}")
        return [], 0
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при получении отфильтрованных пользователей: {e}")
        return [], 0

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


async def apply_user_setting_preset(session: AsyncSession, user_id: int, preset_id: str) -> User | None:
    """Атомарно применяет пресет настроек пользователя и инвалидирует кэш аналитики."""
    try:
        normalized_preset_id = preset_id.strip().upper()
        preset = config.SETTING_PRESETS.get(normalized_preset_id)
        if preset is None:
            logger.warning("Неизвестный preset_id=%s для пользователя %s", preset_id, user_id)
            return None

        # Малые MCAP-значения вида 0.005 записываем как есть, без round(),
        # чтобы не терять точность при подготовке UPDATE.
        update_values = {
            "threshold": float(preset.threshold),
            "threshold_cascade": float(preset.threshold_cascade),
            "threshold_oi_percent": float(preset.threshold_oi_percent),
            "threshold_oi_value": float(preset.threshold_oi_value),
            "threshold_mcap_pct": float(preset.threshold_mcap_pct),
            "threshold_mcap_usd_min": float(preset.threshold_mcap_usd_min),
            "threshold_cascade_mcap_pct": float(preset.threshold_cascade_mcap_pct),
            "threshold_cascade_mcap_usd_min": float(preset.threshold_cascade_mcap_usd_min),
            "filter_rsi_min": float(preset.rsi_min),
            "filter_rsi_max": float(preset.rsi_max),
            "alert_cascade": bool(preset.alert_cascade),
            "alert_volume": bool(preset.alert_volume),
            "alert_squeeze": bool(preset.alert_squeeze),
            "alert_longs": bool(preset.alert_longs),
            "alert_shorts": bool(preset.alert_shorts),
            "alert_oi": bool(preset.alert_oi),
            "alert_rsi": bool(preset.alert_rsi),
            "alert_cvd": bool(preset.alert_cvd),
            # threshold_mode добавляем последним на уровне приложения,
            # чтобы сначала подготовить все числовые пороги пресета.
            "threshold_mode": str(preset.threshold_mode).upper(),
        }

        result = await session.execute(
            update(User)
            .where(User.id == user_id)
            .values(**update_values)
            .execution_options(synchronize_session=False)
        )
        if result.rowcount == 0:
            await session.rollback()
            return None

        await session.commit()
        user = await session.get(User, user_id)
        if user is None:
            return None

        from src.services.analyzer import invalidate_user_cache

        await invalidate_user_cache(user.id)
        return user
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"Ошибка БД при применении пресета {preset_id} для {user_id}: {e}")
        return None
    except Exception as e:
        await session.rollback()
        logger.error(f"Непредвиденная ошибка при применении пресета {preset_id} для {user_id}: {e}")
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
