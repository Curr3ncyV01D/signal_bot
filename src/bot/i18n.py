from typing import Any

from aiogram.types import User as TelegramUser
from aiogram_i18n import I18nMiddleware
from aiogram_i18n.cores.fluent_runtime_core import FluentRuntimeCore
from aiogram_i18n.managers.base import BaseManager
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.localization import (
    DEFAULT_LOCALE,
    LOCALES_DIR,
    normalize_locale_code,
    resolve_initial_locale,
)
from src.database.models import User
from src.database.session import async_session
from src.services.analyzer import invalidate_user_cache


class UserLocaleManager(BaseManager):
    """
    Resolves locale from the persisted user profile and keeps workers in sync
    when the locale is changed through `set_locale`.
    """

    async def set_locale(
        self,
        locale: str,
        event_from_user: TelegramUser | None = None,
        session: AsyncSession | None = None,
        **_: Any,
    ) -> None:
        if event_from_user is None:
            return

        normalized_locale = normalize_locale_code(locale)
        if session is not None:
            user = await session.get(User, event_from_user.id)
            if user is None or user.language_code == normalized_locale:
                return
            user.language_code = normalized_locale
            await session.commit()
            await invalidate_user_cache(event_from_user.id)
            return

        async with async_session() as fallback_session:
            user = await fallback_session.get(User, event_from_user.id)
            if user is None or user.language_code == normalized_locale:
                return
            user.language_code = normalized_locale
            await fallback_session.commit()

        await invalidate_user_cache(event_from_user.id)

    async def get_locale(
        self,
        event_from_user: TelegramUser | None = None,
        session: AsyncSession | None = None,
        **_: Any,
    ) -> str:
        if event_from_user is None:
            return DEFAULT_LOCALE

        if session is not None:
            user = await session.get(User, event_from_user.id)
            if user is not None:
                return normalize_locale_code(user.language_code)

        async with async_session() as fallback_session:
            user = await fallback_session.get(User, event_from_user.id)
            if user is not None:
                return normalize_locale_code(user.language_code)

        return resolve_initial_locale(event_from_user.language_code)


def build_i18n_middleware() -> I18nMiddleware:
    core = FluentRuntimeCore(
        path=LOCALES_DIR,
        default_locale=DEFAULT_LOCALE,
        raise_key_error=True,
    )
    return I18nMiddleware(
        core=core,
        manager=UserLocaleManager(default_locale=DEFAULT_LOCALE),
        default_locale=DEFAULT_LOCALE,
    )
