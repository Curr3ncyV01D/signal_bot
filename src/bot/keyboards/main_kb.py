from math import ceil
from datetime import datetime
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram_i18n import LazyProxy
from aiogram_i18n.types import InlineKeyboardMarkup, InlineKeyboardButton
from src.core.config import config
from src.database.models import User
from src.database.functions import get_utc_now
from src.bot.utils.kb_helper import Kb_Helper
from src.utils import format_smart_num


def _get_days_left(subscription_end: datetime | None, now: datetime) -> int | None:
    """Возвращает количество оставшихся полных/частичных суток активной подписки."""
    if subscription_end is None or subscription_end <= now:
        return None

    seconds_left = (subscription_end - now).total_seconds()
    return max(0, ceil(seconds_left / 86400))

def get_start_kb(user: User) -> InlineKeyboardMarkup:
    """Клавиатура для главного меню (/start)"""
    builder = InlineKeyboardBuilder()
    now = get_utc_now()
    
    # Проверяем активна ли подписка
    has_sub = user.subscription_end and user.subscription_end > now
    days_left = _get_days_left(user.subscription_end, now)
    
    if not user.is_trial_used:
        builder.row(InlineKeyboardButton(text=LazyProxy("kb-main-trial"), callback_data="activate_trial"))

    if (
        not user.is_community_bonus_used
        and user.is_trial_used
        and config.COMMUNITY_GROUP_ID is not None
        and config.COMMUNITY_GROUP_LINK
    ):
        builder.row(
            InlineKeyboardButton(
                text=LazyProxy("kb-main-community-bonus"),
                callback_data="open_community_bonus",
            )
        )

    if not has_sub:
        builder.row(InlineKeyboardButton(text=LazyProxy("kb-main-renew"), callback_data="buy_subscription"))
    else:
        if days_left is not None and days_left <= 5:
            builder.row(
                InlineKeyboardButton(
                    text=LazyProxy("kb-main-renew-left", days=days_left),
                    callback_data="buy_subscription",
                )
            )

        
    builder.row(InlineKeyboardButton(
        text=LazyProxy("kb-main-wallet", balance=format_smart_num(user.balance)),
        callback_data="wallet_main"
    ))
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-main-profile"), callback_data="profile_main"))
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-main-settings"), callback_data="open_settings"))
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-main-support"), url=config.SUPPORT_URL))
    return builder.as_markup()

def get_back_button_kb(back_data: str) -> InlineKeyboardMarkup:
    """Клавиатура для возврата в главное меню"""
    return Kb_Helper.add_common_buttons(InlineKeyboardBuilder(), back_data=back_data).as_markup()


def get_close_button_kb() -> InlineKeyboardMarkup:
    """Клавиатура для сообщений уведомлений. Нужно чтобы закрывать их одной кнопкой"""
    return Kb_Helper.add_common_buttons(InlineKeyboardBuilder()).as_markup()
