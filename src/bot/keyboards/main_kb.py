from math import ceil
from datetime import datetime
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
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


def _format_days_label(days: int) -> str:
    """Возвращает число дней с корректным русским склонением."""
    if 11 <= days % 100 <= 14:
        suffix = "дней"
    else:
        last_digit = days % 10
        if last_digit == 1:
            suffix = "день"
        elif 2 <= last_digit <= 4:
            suffix = "дня"
        else:
            suffix = "дней"

    return f"{days} {suffix}"

def get_start_kb(user: User) -> InlineKeyboardMarkup:
    """Клавиатура для главного меню (/start)"""
    builder = InlineKeyboardBuilder()
    now = get_utc_now()
    
    # Проверяем активна ли подписка
    has_sub = user.subscription_end and user.subscription_end > now
    days_left = _get_days_left(user.subscription_end, now)
    
    if not user.is_trial_used:
        builder.row(InlineKeyboardButton(text="🎁 Пробный период на 24ч", callback_data="activate_trial"))

    if not has_sub:
        builder.row(InlineKeyboardButton(text="⚡️ Продлить подписку", callback_data="buy_subscription"))
    else:
        builder.row(InlineKeyboardButton(text="🚀 Зайти в закрытый канал", callback_data="get_channel_link"))
        if days_left is not None and days_left <= 5:
            builder.row(InlineKeyboardButton(text=f"⚡️ Продлить подписку (осталось {_format_days_label(days_left)})", callback_data="buy_subscription"))

        
    builder.row(InlineKeyboardButton(
        text=f"💰 Кошелек ({format_smart_num(user.balance)} USDT)",
        callback_data="wallet_main"
    ))
    builder.row(InlineKeyboardButton(text="⚙️ Настройки и фильтры", callback_data="open_settings"))
    builder.row(InlineKeyboardButton(text="👨‍💻 Тех. поддержка", url=config.SUPPORT_URL))
    return builder.as_markup()

def get_back_button_kb(back_data: str) -> InlineKeyboardMarkup:
    """Клавиатура для возврата в главное меню"""
    return Kb_Helper.add_common_buttons(InlineKeyboardBuilder(), back_data=back_data).as_markup()


def get_close_button_kb() -> InlineKeyboardMarkup:
    """Клавиатура для сообщений уведомлений. Нужно чтобы закрывать их одной кнопкой"""
    return Kb_Helper.add_common_buttons(InlineKeyboardBuilder()).as_markup()
