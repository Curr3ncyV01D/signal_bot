import logging
from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery

from src.database.session import async_session
from src.database.models import User

logger = logging.getLogger(__name__)

class IsAdminFilter(BaseFilter):
    """
    Фильтр проверяет, является ли пользователь администратором (is_admin == True в БД).
    Поддерживает как сообщения (Message), так и нажатия кнопок (CallbackQuery).
    """
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user_id = event.from_user.id
        
        try:
            async with async_session() as session:
                user = await session.get(User, user_id)
                if user and user.is_admin:
                    return True
                return False
        except Exception as e:
            logger.error(f"Ошибка при проверке прав администратора для {user_id}: {e}")
            return False