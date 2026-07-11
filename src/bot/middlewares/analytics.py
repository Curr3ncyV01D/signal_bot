import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.database.crud.stats_service import log_user_event
from src.database.models import User

logger = logging.getLogger(__name__)
MAX_EVENT_DATA_LENGTH = 255


class AnalyticsMiddleware(BaseMiddleware):
    def __init__(self, session_pool: async_sessionmaker[AsyncSession]):
        super().__init__()
        self.session_pool = session_pool

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        analytics_payload = self._extract_analytics_payload(event)
        result = await handler(event, data)

        if analytics_payload is None:
            return result

        user_id, event_type, event_data = analytics_payload
        asyncio.create_task(self._log_event_in_background(user_id, event_type, event_data))
        return result

    def _extract_analytics_payload(
        self,
        event: TelegramObject,
    ) -> tuple[int, str, str] | None:
        if isinstance(event, Message):
            if event.from_user is None or not event.text or not event.text.startswith("/"):
                return None
            return (
                event.from_user.id,
                "COMMAND",
                event.text[:MAX_EVENT_DATA_LENGTH],
            )

        if isinstance(event, CallbackQuery):
            if event.from_user is None or not event.data:
                return None
            return (
                event.from_user.id,
                "CALLBACK",
                event.data[:MAX_EVENT_DATA_LENGTH],
            )

        return None

    async def _log_event_in_background(
        self,
        user_id: int,
        event_type: str,
        event_data: str,
    ) -> None:
        try:
            async with self.session_pool() as session:
                user = await session.get(User, user_id)
                if user is None:
                    logger.debug(
                        "Пропуск логирования аналитики: пользователь %s не найден.",
                        user_id,
                    )
                    return

                await log_user_event(
                    session=session,
                    user_id=user.id,
                    event_type=event_type,
                    data=event_data,
                    is_admin=user.is_admin,
                )
        except Exception:
            logger.exception(
                "Непредвиденная ошибка фонового логирования события %s для пользователя %s.",
                event_type,
                user_id,
            )
