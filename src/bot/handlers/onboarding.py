import logging

from aiogram import F, Router, types
from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram_i18n import I18nContext
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import ImagePaths, config
from src.core.dto import SettingPresetId
from src.core.localization import normalize_locale_code
from src.database.crud import billing_service
from src.database.crud.user_service import (
    apply_user_setting_preset,
    complete_user_setup,
    get_or_create_user,
)
from src.database.models import User
from src.services.analyzer import invalidate_user_cache
from src.utils import format_smart_num

logger = logging.getLogger(__name__)
router = Router()
PRESET_ORDER: tuple[SettingPresetId, ...] = ("SCALPER", "BALANCED", "CONSERVATIVE")


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
        try:
            await event.message.delete()
        except Exception:
            pass
        await event.message.answer_photo(
            photo=FSInputFile(ImagePaths.WELCOME),
            caption=caption,
            reply_markup=reply_markup,
            parse_mode="HTML",
        )


def get_presets_selection_kb(i18n: I18nContext) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=i18n.get("onboarding-preset-button-scalper"),
            callback_data="apply_onboarding_preset_SCALPER",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=i18n.get("onboarding-preset-button-balanced"),
            callback_data="apply_onboarding_preset_BALANCED",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=i18n.get("onboarding-preset-button-conservative"),
            callback_data="apply_onboarding_preset_CONSERVATIVE",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=i18n.get("onboarding-preset-button-skip"),
            callback_data="skip_onboarding_preset",
        )
    )
    return builder.as_markup()


def _build_presets_selection_caption(i18n: I18nContext) -> str:
    scalper = config.SETTING_PRESETS["SCALPER"]
    balanced = config.SETTING_PRESETS["BALANCED"]
    conservative = config.SETTING_PRESETS["CONSERVATIVE"]
    return i18n.get(
        "onboarding-presets-screen",
        scalper_mode=scalper.threshold_mode,
        scalper_threshold=format_smart_num(scalper.threshold),
        scalper_cascade=format_smart_num(scalper.threshold_cascade),
        scalper_oi_percent=format_smart_num(scalper.threshold_oi_percent, is_percent=True, decimal_places=1),
        scalper_oi_value=format_smart_num(scalper.threshold_oi_value),
        balanced_mode=balanced.threshold_mode,
        balanced_threshold=format_smart_num(balanced.threshold),
        balanced_cascade=format_smart_num(balanced.threshold_cascade),
        balanced_oi_percent=format_smart_num(balanced.threshold_oi_percent, is_percent=True, decimal_places=1),
        balanced_oi_value=format_smart_num(balanced.threshold_oi_value),
        conservative_mode=conservative.threshold_mode,
        conservative_threshold=format_smart_num(conservative.threshold),
        conservative_cascade=format_smart_num(conservative.threshold_cascade),
        conservative_oi_percent=format_smart_num(conservative.threshold_oi_percent, is_percent=True, decimal_places=1),
        conservative_oi_value=format_smart_num(conservative.threshold_oi_value),
    )


async def render_presets_selection_screen(
    event: types.Message | types.CallbackQuery,
    i18n: I18nContext,
) -> None:
    """Показывает шаг выбора профиля стратегии с возможностью пропуска."""
    caption = _build_presets_selection_caption(i18n)
    reply_markup = get_presets_selection_kb(i18n)
    photo = FSInputFile(ImagePaths.SETTINGS)

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
        logger.warning(f"Не удалось показать выбор пресетов через edit_media: {exc}")
        try:
            await event.message.delete()
        except Exception:
            pass
        await event.message.answer_photo(
            photo=FSInputFile(ImagePaths.SETTINGS),
            caption=caption,
            reply_markup=reply_markup,
            parse_mode="HTML",
        )


def _is_community_bonus_available() -> bool:
    return config.COMMUNITY_GROUP_ID is not None and bool(config.COMMUNITY_GROUP_LINK)


def _resolve_onboarding_step(user: User) -> str:
    step = str(getattr(user, "onboarding_step", "LANGUAGE") or "LANGUAGE")
    if step == "COMMUNITY_BONUS" and (not _is_community_bonus_available() or user.is_community_bonus_used):
        return "PRESET_SELECTION"
    if step not in {"LANGUAGE", "COMMUNITY_BONUS", "PRESET_SELECTION", "COMPLETED"}:
        return "LANGUAGE"
    return step


async def render_pending_onboarding_screen(
    event: types.Message | types.CallbackQuery,
    user: User,
    i18n: I18nContext,
) -> None:
    """Рендерит актуальный шаг незавершенного онбординга."""
    step = _resolve_onboarding_step(user)
    if step == "COMMUNITY_BONUS":
        await render_community_bonus_screen(event, i18n, show_back_to_main=False)
        return
    if step == "PRESET_SELECTION":
        await render_presets_selection_screen(event, i18n)
        return
    await render_onboarding_language_screen(event, i18n)


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
        try:
            await event.message.delete()
        except Exception:
            pass
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
    """Сохраняет выбранный язык и переводит пользователя на следующий шаг мастера."""
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
    user.onboarding_step = (
        "COMMUNITY_BONUS"
        if _is_community_bonus_available() and not user.is_community_bonus_used
        else "PRESET_SELECTION"
    )
    try:
        await session.commit()
        await session.refresh(user)
    except Exception as exc:
        await session.rollback()
        logger.error("Не удалось сохранить шаг онбординга для %s: %s", user.id, exc)
        await callback.answer(i18n.get("settings-error-save"), show_alert=True)
        return

    await invalidate_user_cache(user.id)

    with i18n.use_locale(selected_locale):
        await render_pending_onboarding_screen(callback, user, i18n)
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

    user.onboarding_step = "PRESET_SELECTION"
    try:
        await session.commit()
        await session.refresh(user)
    except Exception as exc:
        await session.rollback()
        logger.error("Не удалось перевести пользователя %s на выбор пресета: %s", user.id, exc)
        await callback.answer(i18n.get("settings-error-save"), show_alert=True)
        return

    await render_presets_selection_screen(callback, i18n)
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

    user.onboarding_step = "PRESET_SELECTION"
    await session.commit()
    await session.refresh(user)
    await render_presets_selection_screen(callback, i18n)
    await callback.answer(i18n.get("community-bonus-granted-toast", hours=config.COMMUNITY_BONUS_HOURS))


@router.callback_query(F.data.startswith("apply_onboarding_preset_"))
async def process_apply_onboarding_preset(
    callback: types.CallbackQuery,
    session: AsyncSession,
    i18n: I18nContext,
) -> None:
    preset_id = callback.data.removeprefix("apply_onboarding_preset_").upper()
    if preset_id not in PRESET_ORDER:
        await callback.answer(i18n.get("settings-error-save"), show_alert=True)
        return

    user = await apply_user_setting_preset(session, callback.from_user.id, preset_id)
    if user is None:
        await callback.answer(i18n.get("settings-error-save"), show_alert=True)
        return

    completed_user = await complete_user_setup(session, callback.from_user.id)
    if completed_user is None:
        await callback.answer(i18n.get("settings-error-save"), show_alert=True)
        return

    from src.bot.handlers.commands import render_main_menu

    await render_main_menu(callback, completed_user, callback.from_user.full_name, i18n)
    await callback.answer(
        i18n.get(
            f"onboarding-preset-applied-{preset_id.lower()}",
        )
    )


@router.callback_query(F.data == "skip_onboarding_preset")
async def process_skip_onboarding_preset(
    callback: types.CallbackQuery,
    session: AsyncSession,
    i18n: I18nContext,
) -> None:
    completed_user = await complete_user_setup(session, callback.from_user.id)
    if completed_user is None:
        await callback.answer(i18n.get("settings-error-save"), show_alert=True)
        return

    from src.bot.handlers.commands import render_main_menu

    await render_main_menu(callback, completed_user, callback.from_user.full_name, i18n)
    await callback.answer(i18n.get("onboarding-preset-skipped"))
