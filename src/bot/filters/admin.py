import logging
from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import User

logger = logging.getLogger(__name__)

class IsAdminFilter(BaseFilter):
    """
    Фильтр проверяет, является ли пользователь администратором (is_admin == True в БД).
    Поддерживает как сообщения (Message), так и нажатия кнопок (CallbackQuery).
    """
    async def __call__(self, event: Message | CallbackQuery, session: AsyncSession) -> bool:
        user_id = event.from_user.id
        
        try:
            user = await session.get(User, user_id)
            if user and user.is_admin:
                return True
            return False
        except Exception as e:
            logger.error(f"Ошибка при проверке прав администратора для {user_id}: {e}")
            return False