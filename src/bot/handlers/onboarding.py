import logging

from aiogram import F, Router, types
from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram_i18n import I18nContext
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import ImagePaths, config
from src.core.localization import normalize_locale_code
from src.database.crud import billing_service
from src.database.crud.user_service import complete_user_setup, get_or_create_user
from src.database.models import User
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


def _is_community_bonus_available() -> bool:
    return config.COMMUNITY_GROUP_ID is not None and bool(config.COMMUNITY_GROUP_LINK)


def get_community_bonus_kb(
    i18n: I18nContext,
    *,
    show_back_to_main: bool,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=i18n.get("community-bonus-button-join"),
            url=config.COMMUNITY_GROUP_LINK,
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=i18n.get("community-bonus-button-verify"),
            callback_data="verify_community_join",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=i18n.get("main-button-home") if show_back_to_main else i18n.get("community-bonus-button-later"),
            callback_data="back_to_main" if show_back_to_main else "dismiss_community_bonus",
        )
    )
    return builder.as_markup()


async def render_community_bonus_screen(
    event: types.Message | types.CallbackQuery,
    i18n: I18nContext,
    *,
    show_back_to_main: bool,
) -> None:
    """Показывает оффер на бонус за вступление в сообщество."""
    caption = i18n.get("community-bonus-screen", hours=config.COMMUNITY_BONUS_HOURS)
    reply_markup = get_community_bonus_kb(i18n, show_back_to_main=show_back_to_main)
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
        logger.warning(f"Не удалось показать community bonus через edit_media: {exc}")
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
        if _is_community_bonus_available() and not completed_user.is_community_bonus_used:
            await render_community_bonus_screen(callback, i18n, show_back_to_main=False)
        else:
            await render_main_menu(
                callback,
                completed_user,
                callback.from_user.full_name,
                i18n,
            )
        await callback.answer(i18n.get("onboarding-language-selected"))


@router.callback_query(F.data == "dismiss_community_bonus")
async def process_dismiss_community_bonus(
    callback: types.CallbackQuery,
    session: AsyncSession,
    i18n: I18nContext,
) -> None:
    user = await session.get(User, callback.from_user.id)
    if not user:
        await callback.answer(i18n.get("profile-not-found-start"), show_alert=True)
        return

    from src.bot.handlers.commands import render_main_menu

    await render_main_menu(callback, user, callback.from_user.full_name, i18n)
    await callback.answer(i18n.get("community-bonus-later-toast"))


@router.callback_query(F.data == "open_community_bonus")
async def process_open_community_bonus(
    callback: types.CallbackQuery,
    session: AsyncSession,
    i18n: I18nContext,
) -> None:
    user = await session.get(User, callback.from_user.id)
    if not user:
        await callback.answer(i18n.get("profile-not-found-start"), show_alert=True)
        return

    if user.is_community_bonus_used:
        await callback.answer(i18n.get("community-bonus-already-used"), show_alert=True)
        return

    if not _is_community_bonus_available():
        await callback.answer(i18n.get("community-bonus-unavailable"), show_alert=True)
        return

    await render_community_bonus_screen(callback, i18n, show_back_to_main=True)
    await callback.answer()


@router.callback_query(F.data == "verify_community_join")
async def process_verify_community_join(
    callback: types.CallbackQuery,
    session: AsyncSession,
    i18n: I18nContext,
) -> None:
    if not _is_community_bonus_available():
        await callback.answer(i18n.get("community-bonus-unavailable"), show_alert=True)
        return

    user = await session.get(User, callback.from_user.id)
    if not user:
        await callback.answer(i18n.get("profile-not-found-start"), show_alert=True)
        return

    if user.is_community_bonus_used:
        await callback.answer(i18n.get("community-bonus-already-used"), show_alert=True)
        return

    try:
        member = await callback.bot.get_chat_member(
            chat_id=config.COMMUNITY_GROUP_ID,
            user_id=callback.from_user.id,
        )
    except Exception as exc:
        logger.warning("Не удалось проверить участие пользователя %s в community: %s", callback.from_user.id, exc)
        await callback.answer(i18n.get("community-bonus-verification-error"), show_alert=True)
        return

    if member.status not in {"member", "administrator", "creator"}:
        await callback.answer(i18n.get("community-bonus-join-required"), show_alert=True)
        return

    success, _ = await billing_service.apply_community_bonus(session, callback.from_user.id)
    if not success:
        await session.rollback()
        await callback.answer(i18n.get("community-bonus-activation-failed"), show_alert=True)
        return

    await session.commit()
    await session.refresh(user)

    from src.bot.handlers.commands import render_main_menu

    await render_main_menu(callback, user, callback.from_user.full_name, i18n)
    await callback.answer(i18n.get("community-bonus-granted-toast", hours=config.COMMUNITY_BONUS_HOURS))
