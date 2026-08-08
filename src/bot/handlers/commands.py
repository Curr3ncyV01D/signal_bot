import asyncio
import logging
from datetime import datetime, timezone
from aiogram import Router, types, F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile, InputMediaPhoto
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest
from aiogram_i18n import I18nContext
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import config
from src.core.config import ImagePaths
from src.database.crud import billing_service, user_service
from src.database.crud.user_service import get_or_create_user
from src.database.models import User
from src.database.functions import get_utc_now
from src.bot.handlers.onboarding import render_pending_onboarding_screen
from src.bot.keyboards import get_start_kb, get_status_kb
from src.services.analyzer import invalidate_user_cache
from src.services.metrics_service import MetricsService
from src.utils import format_datetime, format_smart_num

logger = logging.getLogger(__name__)
router = Router()


async def render_main_menu(
    event: types.Message | types.CallbackQuery,
    user: User,
    full_name: str,
    i18n: I18nContext,
) -> None:
    """Умный рендеринг главного меню с баннером WELCOME."""
    text = get_main_menu_text(user, full_name, i18n)
    markup = get_start_kb(user)
    photo = FSInputFile(ImagePaths.WELCOME)

    if isinstance(event, types.Message):
        await event.answer_photo(
            photo=photo,
            caption=text,
            reply_markup=markup,
            parse_mode="HTML"
        )
        return

    try:
        await event.message.edit_media(
            media=InputMediaPhoto(
                media=photo,
                caption=text,
                parse_mode="HTML"
            ),
            reply_markup=markup
        )
    except Exception as e:
        logger.warning(f"Не удалось обновить главное меню через edit_media: {e}")
        try:
            await event.message.delete()
        except Exception:
            pass
        await event.message.answer_photo(
            photo=FSInputFile(ImagePaths.WELCOME),
            caption=text,
            reply_markup=markup,
            parse_mode="HTML"
        )

async def _get_news_channel_url(bot) -> str | None:
    if config.NEWS_CHANNEL_ID is None:
        return None
    if config.NEWS_CHANNEL_URL:
        return config.NEWS_CHANNEL_URL
    try:
        chat = await bot.get_chat(config.NEWS_CHANNEL_ID)
        if getattr(chat, "username", None):
            return f"https://t.me/{chat.username}"
    except Exception as e:
        logger.error(f"Не удалось получить URL новостного канала: {e}")
    return None

async def _build_trial_subscription_kb(bot, i18n: I18nContext) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    news_channel_url = await _get_news_channel_url(bot)
    if news_channel_url:
        builder.row(
            InlineKeyboardButton(text=i18n.get("trial-button-news-channel"), url=news_channel_url)
        )
    builder.row(
        InlineKeyboardButton(
            text=i18n.get("trial-button-check-subscription"),
            callback_data="confirm_trial_activation"
        )
    )
    return builder.as_markup()

def get_main_menu_text(user: User, full_name: str, i18n: I18nContext) -> str:
    """Текст главного меню."""
    now = get_utc_now()
    has_sub = user.subscription_end and user.subscription_end > now
    
    status_text = (
        i18n.get("main-menu-status-active", subscription_end=format_datetime(user.subscription_end))
        if has_sub
        else i18n.get("main-menu-status-inactive")
    )
    
    return i18n.get(
        "main-menu",
        full_name=full_name,
        subscription_status=status_text,
        balance=format_smart_num(user.balance),
    )


@router.message(Command("start"))
async def cmd_start(message: types.Message, session: AsyncSession, i18n: I18nContext):
    # Парсинг реферального кода из команды (например: /start ref_12345 или /start 12345)
    referrer_id = None
    if message.text and len(message.text.split()) > 1:
        ref_arg = message.text.split()[1]
        ref_arg = ref_arg.replace("ref_", "")
        if ref_arg.isdigit():
            parsed_ref = int(ref_arg)
            # Запрещаем указывать самого себя как реферера
            if parsed_ref != message.from_user.id:
                referrer_id = parsed_ref

    user = await get_or_create_user(
        session, 
        message.from_user.id, 
        message.from_user.username,
        referrer_id=referrer_id,
        telegram_language_code=message.from_user.language_code,
    )
    if user is None:
        await message.answer(i18n.get("profile-not-found-start"))
        return

    if not user.is_setup_completed:
        await render_pending_onboarding_screen(message, user, i18n)
        return

    await render_main_menu(message, user, message.from_user.full_name, i18n)

@router.callback_query(F.data == "back_to_main")
async def process_back_to_main(callback: types.CallbackQuery, session: AsyncSession, i18n: I18nContext):
    """Возврат в главное меню из настроек"""
    user = await session.get(User, callback.from_user.id)
    if not user:
        return await callback.answer(i18n.get("settings-error-profile"), show_alert=True)

    if not user.is_setup_completed:
        await render_pending_onboarding_screen(callback, user, i18n)
        await callback.answer()
        return

    await render_main_menu(callback, user, callback.from_user.full_name, i18n)
    await callback.answer()

@router.callback_query(F.data == "activate_trial")
async def process_activate_trial(callback: types.CallbackQuery, i18n: I18nContext):
    """Показывает экран предложения триала и переход в новостной канал."""
    if config.NEWS_CHANNEL_ID is None:
        return await callback.answer(
            i18n.get("trial-unavailable-news-channel"),
            show_alert=True,
        )

    text = i18n.get("trial-screen")
    markup = await _build_trial_subscription_kb(callback.bot, i18n)
    photo = FSInputFile(ImagePaths.WELCOME)

    try:
        await callback.message.edit_media(
            media=InputMediaPhoto(
                media=photo,
                caption=text,
                parse_mode="HTML"
            ),
            reply_markup=markup
        )
    except Exception as e:
        logger.warning(f"Не удалось обновить экран условий триала через edit_media: {e}")
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer_photo(
            photo=photo,
            caption=text,
            reply_markup=markup,
            parse_mode="HTML"
        )
    await callback.answer()

@router.callback_query(F.data == "confirm_trial_activation")
async def process_confirm_trial(callback: types.CallbackQuery, session: AsyncSession, i18n: I18nContext):
    """Активирует триал без проверки подписки на новостной канал."""
    if config.NEWS_CHANNEL_ID is None:
        return await callback.answer(
            i18n.get("trial-mode-disabled"),
            show_alert=True,
        )

    user = await session.get(User, callback.from_user.id)
    if not user:
        return await callback.answer(i18n.get("profile-not-found-start"), show_alert=True)

    if user.is_trial_used:
        return await callback.answer(i18n.get("trial-already-used"), show_alert=True)

    success, msg = await user_service.activate_trial(session, callback.from_user.id)
    if not success:
        await session.rollback()
        return await callback.answer(msg, show_alert=True)

    activated, new_end = await billing_service.issue_bonus_subscription(
        session=session,
        user_id=callback.from_user.id,
        hours=config.TRIAL_DURATION_DAYS * 24,
        internal_description="billing-tx-trial-description",
        locale=user.language_code,
    )
    if not activated or not new_end:
        await session.rollback()
        return await callback.answer(i18n.get("trial-activation-failed"), show_alert=True)

    await session.commit()
    await invalidate_user_cache(callback.from_user.id)

    success_text = i18n.get("trial-activated-screen")
    
    builder = InlineKeyboardBuilder()
    news_channel_url = await _get_news_channel_url(callback.bot)
    if news_channel_url:
        builder.row(
            InlineKeyboardButton(
                text=i18n.get("trial-button-news-channel"),
                url=news_channel_url,
            )
        )
    builder.row(InlineKeyboardButton(text=i18n.get("kb-main-settings"), callback_data="open_settings"))
    builder.row(InlineKeyboardButton(text=i18n.get("main-button-home"), callback_data="back_to_main"))
    markup = builder.as_markup()
    
    photo = FSInputFile(ImagePaths.WELCOME)

    try:
        await callback.message.edit_media(
            media=InputMediaPhoto(
                media=photo,
                caption=success_text,
                parse_mode="HTML"
            ),
            reply_markup=markup
        )
    except Exception as e:
        logger.warning(f"Не удалось показать экран успеха триала через edit_media: {e}")
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer_photo(
            photo=photo,
            caption=success_text,
            reply_markup=markup,
            parse_mode="HTML"
        )
    
    await callback.answer(i18n.get("trial-activated-toast"))

async def generate_status_text(listener, liq_aggregator, data_queue: asyncio.Queue, i18n: I18nContext) -> str:
    """Хелпер для генерации текста статуса (используется в команде и кнопке Обновить)"""
    stats = await MetricsService.get_system_stats(listener, liq_aggregator, data_queue)
    latency = MetricsService.get_analytics_latency(listener)

    active_pool = stats["active_connections"]
    total_pool = stats["total_connections"]

    status_emoji = "✅" if active_pool >= max(1, total_pool * 3 / 4) else "⚠️"
    if active_pool == 0: status_emoji = "❌"

    queue_size = stats["queue_size"]
    queue_status = "🟢" if queue_size < 50 else "🟡" if queue_size < 200 else "🔴"

    return i18n.get(
        "status-screen",
        status_emoji=status_emoji,
        title=i18n.get("system-status-title"),
        active_pool=active_pool,
        total_pool=total_pool,
        latency=latency,
        active_symbols=stats["active_symbols"],
        total_events=stats["total_events"],
        queue_status=queue_status,
        queue_size=queue_size,
        cpu_pct="{:.1f}".format(stats["process_cpu_pct"]),
        ram_pct="{:.2f}".format(stats["process_ram_pct"]),
        uptime=stats["uptime"],
        server_time=stats["server_time"],
    )

@router.message(Command("status"))
async def cmd_status(message: types.Message, listener, liq_aggregator, data_queue: asyncio.Queue, i18n: I18nContext):
    """Вызов статуса через команду"""
    try:
        await message.delete()
    except Exception:
        pass
    text = await generate_status_text(listener, liq_aggregator, data_queue, i18n)
    await message.answer(text, reply_markup=get_status_kb(), parse_mode="HTML")

@router.callback_query(F.data == "refresh_status")
async def process_refresh_status(callback: types.CallbackQuery, listener, liq_aggregator, data_queue: asyncio.Queue, i18n: I18nContext):
    """Обновление статуса по кнопке (меняет текст сообщения)"""
    text = await generate_status_text(listener, liq_aggregator, data_queue, i18n)
    try:
        await callback.message.edit_text(text, reply_markup=get_status_kb(), parse_mode="HTML")
        await callback.answer(i18n.get("status-refresh-success"))
    except TelegramBadRequest as e:
        # Игнорируем ошибку "Message is not modified", если за секунду статус не поменялся
        if "message is not modified" in str(e).lower():
            await callback.answer(i18n.get("status-refresh-no-changes"), show_alert=False)
        else:
            logger.error(f"Ошибка при обновлении статуса: {e}")
            await callback.answer(i18n.get("status-refresh-error"), show_alert=True)
