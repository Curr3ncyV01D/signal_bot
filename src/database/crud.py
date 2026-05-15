from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from datetime import datetime, timedelta, timezone
from src.database.models import Liquidation, User

import logging

logger = logging.getLogger(__name__)

async def save_liquidation(session: AsyncSession, item: dict):
    """Сохранение одной ликвидации в базу"""
    try:
        # Извлекаем данные (учитываем оба варианта ключей V5)
        symbol = item.get("s") or item.get("symbol")
        side = item.get("S") or item.get("side")
        
        # Защита от некорректных типов данных
        try:
            price = float(item.get("p") or item.get("price", 0))
            qty = float(item.get("v") or item.get("qty", 0))
        except (ValueError, TypeError):
            logger.warning(f"Пропуск ликвидации из-за некорректных чисел: {item}")
            return
        
        if not symbol or price <= 0 or qty <= 0:
            return

        new_liq = Liquidation(
            symbol=symbol,
            side=side,
            price=price,
            qty=qty,
            value = round(price * qty, 2),
            timestamp=datetime.now(timezone.utc).replace(tzinfo=None)
        )
        
        session.add(new_liq)
        await session.commit()
    except Exception as e:
        await session.rollback()
        logger.error(f"Ошибка сохранения в БД: {e}")

async def get_or_create_user(session: AsyncSession, user_id: int, username: str):
    """Регистрация пользователя в базе"""
    try:
        user = await session.get(User, user_id)
        
        # Если пользователь существует, возвращаем его
        if user:
            # Обновляем username, если он изменился
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
        # Попытка вернуть пользователя после роллбэка, если он уже был создан
        try:
            return await session.get(User, user_id)
        except:
            return None

async def get_active_users(session: AsyncSession):
    """Получаем всех пользователей для рассылки"""
    try:
        result = await session.execute(select(User))
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Ошибка при получении списка пользователей: {e}")
        return []

async def get_sum_for_period(session: AsyncSession, symbol: str, minutes: int):
    """Считает сумму ликвидаций по монете за последние N минут"""
    try:
        threshold_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=minutes)
        
        query = (
            select(func.sum(Liquidation.value))
            .where(Liquidation.symbol == symbol)
            .where(Liquidation.timestamp >= threshold_time)
        )
        
        result = await session.execute(query)
        total_value = result.scalar() or 0.0
        return float(total_value)
    except Exception as e:
        logger.error(f"Ошибка при расчете суммы за период ({symbol}, {minutes}m): {e}")
        return 0.0

async def delete_old_liquidations(session: AsyncSession, hours: int = 4):
    """Удаляет записи ликвидаций старше указанного количества часов"""
    try:
        threshold_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=hours)
        query = delete(Liquidation).where(Liquidation.timestamp < threshold_time)
        result = await session.execute(query)
        await session.commit()
        return result.rowcount
    except Exception as e:
        await session.rollback()
        logger.error(f"Ошибка при очистке старых записей: {e}")
        return 0

async def get_recent_liquidations(session: AsyncSession, minutes: int = 60):
    """Получает все ликвидации за последние N минут для прогрева кэша"""
    threshold_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=minutes)
    
    query = (
        select(Liquidation)
        .where(Liquidation.timestamp >= threshold_time)
        .order_by(Liquidation.timestamp.asc()) # Важно: от старых к новым
    )
    
    result = await session.execute(query)
    return result.scalars().all()