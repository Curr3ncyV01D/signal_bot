import logging

from aiogram import F, Router, types
from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram_i18n import I18nContext
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import ImagePaths
from src.core.localization import normalize_locale_code
from src.database.crud.user_service import complete_user_setup, get_or_create_user
from src.services.analyzer import invalidate_user_cache

logger = logging.getLogger(__name__)
router = Router()


def get_onboarding_language_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Русский", callback_data="onboarding_language_ru"),
        InlineKeyboardButton(text="English", callback_data="onboarding_language_en"),
    )
    return builder.as_markup()


async def render_onboarding_language_screen(
    event: types.Message | types.CallbackQuery,
    i18n: I18nContext,
) -> None:
    """Показывает первый экран онбординга с выбором языка."""
    caption = i18n.get("onboarding-language-screen")
    reply_markup = get_onboarding_language_kb()
    photo = FSInputFile(ImagePaths.WELCOME)

    if isinstance(event, types.Message):
        await event.answer_photo(
            photo=photo,
            caption=caption,
            reply_markup=reply_markup,
            parse_mode="HTML",
        )
        return

    try:
        await event.message.edit_media(
            media=InputMediaPhoto(
                media=photo,
                caption=caption,
                parse_mode="HTML",
            ),
            reply_markup=reply_markup,
        )
    except Exception as exc:
        logger.warning(f"Не удалось показать onboarding через edit_media: {exc}")
        await event.message.delete()
        await event.message.answer_photo(
            photo=FSInputFile(ImagePaths.WELCOME),
            caption=caption,
            reply_markup=reply_markup,
            parse_mode="HTML",
        )


@router.callback_query(F.data.startswith("onboarding_language_"))
async def process_onboarding_language(
    callback: types.CallbackQuery,
    session: AsyncSession,
    i18n: I18nContext,
) -> None:
    """Завершает онбординг, сохраняя выбранный язык интерфейса."""
    selected_locale = normalize_locale_code(callback.data.rsplit("_", 1)[-1])
    user = await get_or_create_user(
        session,
        callback.from_user.id,
        callback.from_user.username,
        telegram_language_code=selected_locale,
    )
    if user is None:
        await callback.answer(i18n.get("settings-error-profile"), show_alert=True)
        return

    user.language_code = selected_locale
    completed_user = await complete_user_setup(session, user.id)
    if completed_user is None:
        await callback.answer(i18n.get("settings-error-save"), show_alert=True)
        return

    await invalidate_user_cache(user.id)

    from src.bot.handlers.commands import render_main_menu

    with i18n.use_locale(selected_locale):
        await render_main_menu(
            callback,
            completed_user,
            callback.from_user.full_name,
            i18n,
        )
        await callback.answer(i18n.get("onboarding-language-selected"))
