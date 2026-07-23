import logging

from aiogram import F, Router, types
from aiogram_i18n import I18nContext
from aiogram.types import FSInputFile, InputMediaPhoto
from aiogram.utils.markdown import hbold, hcode
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.handlers.onboarding import render_pending_onboarding_screen
from src.bot.keyboards.billing_kb import get_profile_main_kb, get_wallet_back_kb
from src.core.config import ImagePaths, config
from src.core.localization import DEFAULT_LOCALE, FALLBACK_LOCALE, normalize_locale_code
from src.database.crud import billing_service, user_service
from src.database.models import User
from src.services.analyzer import invalidate_user_cache
from src.utils import format_smart_num

logger = logging.getLogger(__name__)
router = Router()


def _format_language_label(language_code: str) -> str:
    normalized = normalize_locale_code(language_code)
    return "RU" if normalized == DEFAULT_LOCALE else "EN"


def render_profile_text(user: User, i18n: I18nContext) -> str:
    return i18n.get(
        "profile-main-screen",
        user_id=hcode(user.id),
        language=hbold(_format_language_label(user.language_code)),
        balance=hbold(f"{format_smart_num(user.balance)} USDT"),
    )


async def _render_profile_screen(
    event: types.Message | types.CallbackQuery,
    caption: str,
    reply_markup: types.InlineKeyboardMarkup | None = None,
    image_path: str | None = None,
) -> None:
    if isinstance(event, types.Message):
        if image_path:
            await event.answer_photo(
                photo=FSInputFile(image_path),
                caption=caption,
                reply_markup=reply_markup,
                parse_mode="HTML",
            )
        else:
            await event.answer(caption, reply_markup=reply_markup, parse_mode="HTML")
        return

    if image_path:
        try:
            await event.message.edit_media(
                media=InputMediaPhoto(
                    media=FSInputFile(image_path),
                    caption=caption,
                    parse_mode="HTML",
                ),
                reply_markup=reply_markup,
            )
            return
        except Exception:
            pass
    else:
        try:
            await event.message.edit_text(
                caption,
                reply_markup=reply_markup,
                parse_mode="HTML",
            )
            return
        except Exception:
            pass

    await event.message.delete()
    if image_path:
        await event.message.answer_photo(
            photo=FSInputFile(image_path),
            caption=caption,
            reply_markup=reply_markup,
            parse_mode="HTML",
        )
    else:
        await event.message.answer(caption, reply_markup=reply_markup, parse_mode="HTML")


async def _render_profile_home(
    event: types.Message | types.CallbackQuery,
    session: AsyncSession,
    user: User,
    i18n: I18nContext,
) -> None:
    await _render_profile_screen(
        event,
        render_profile_text(user, i18n),
        get_profile_main_kb(user),
        image_path=ImagePaths.SETTINGS,
    )


@router.callback_query(F.data == "profile_main")
async def callback_profile_main(callback: types.CallbackQuery, session: AsyncSession, i18n: I18nContext):
    user = await user_service.get_user_by_id(session, callback.from_user.id)
    if not user:
        user = await user_service.get_or_create_user(
            session,
            callback.from_user.id,
            callback.from_user.username,
            telegram_language_code=callback.from_user.language_code,
        )
    if user is None:
        return await callback.answer(i18n.get("settings-error-profile"), show_alert=True)

    if not user.is_setup_completed:
        await render_pending_onboarding_screen(callback, user, i18n)
        await callback.answer()
        return

    await _render_profile_home(callback, session, user, i18n)
    await callback.answer()


@router.callback_query(F.data.in_({"profile_change_language", "change_language"}))
async def callback_profile_change_language(callback: types.CallbackQuery, session: AsyncSession, i18n: I18nContext):
    user = await user_service.get_user_by_id(session, callback.from_user.id)
    if not user:
        return await callback.answer(i18n.get("settings-error-profile"), show_alert=True)

    current_locale = normalize_locale_code(user.language_code)
    new_locale = FALLBACK_LOCALE if current_locale == DEFAULT_LOCALE else DEFAULT_LOCALE

    user.language_code = new_locale
    await session.commit()
    await session.refresh(user)
    await invalidate_user_cache(user.id)

    with i18n.use_locale(new_locale):
        await _render_profile_home(callback, session, user, i18n)
        await callback.answer(i18n.get("wallet-language-changed"))


@router.callback_query(F.data.in_({"profile_partner_cabinet", "partner_cabinet"}))
async def callback_profile_partner_cabinet(callback: types.CallbackQuery, session: AsyncSession, i18n: I18nContext):
    bot_info = await callback.bot.get_me()
    referral_link = f"https://t.me/{bot_info.username}?start={callback.from_user.id}"

    invited_count, total_rewards = await billing_service.get_partner_stats(session, callback.from_user.id)

    text = i18n.get(
        "wallet-partner-screen",
        bonus_percent=config.REFERRAL_BONUS_PERCENT,
        referral_link=hcode(referral_link),
        invited_count=hbold(str(invited_count)),
        total_rewards=hbold(f"{format_smart_num(total_rewards)} USDT"),
    )
    await _render_profile_screen(callback, text, get_wallet_back_kb("profile_main"), image_path=ImagePaths.AFFILIATE)
    await callback.answer()
