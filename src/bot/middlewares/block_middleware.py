import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Update
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.core.security import SecurityManager

logger = logging.getLogger(__name__)

class BlockMiddleware(BaseMiddleware):
    def __init__(self, session_pool: async_sessionmaker):
        self.session_pool = session_pool

    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any],
    ) -> Any:
        # Получаем user_id из сообщения или коллбэка
        user_id = None
        if event.message:
            user_id = event.message.from_user.id
        elif event.callback_query:
            user_id = event.callback_query.from_user.id
        elif event.chat_join_request:
            user_id = event.chat_join_request.from_user.id

        if user_id:
            # Мгновенная проверка через SecurityManager
            if SecurityManager.is_blocked(user_id):
                logger.info(f"🚫 Заблокированный пользователь {user_id} пытался совершить действие.")
                
                # Если это сообщение, можно ответить (опционально)
                if event.message:
                    try:
                        await event.message.answer("❌ Доступ к боту ограничен администрацией.")
                    except:
                        pass
                return

        return await handler(event, data)