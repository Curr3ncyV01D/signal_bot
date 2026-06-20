from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.types import Message


class FSMCleanerMiddleware(BaseMiddleware):
    """Очищает состояние FSM, если пользователь ввел команду, начинающуюся с /"""
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        state = data.get("state")
        if (
            isinstance(event, Message)
            and event.text
            and event.text.startswith("/")
            and isinstance(state, FSMContext)
        ):
            await state.clear()

        return await handler(event, data)
