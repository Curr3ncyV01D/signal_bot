from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from src.database.models import User
from src.database.functions import get_utc_now
from src.bot.utils.kb_helper import Kb_Helper

def get_start_kb(user: User) -> InlineKeyboardMarkup:
    """Клавиатура для главного меню (/start)"""
    builder = InlineKeyboardBuilder()
    now = get_utc_now()
    
    # Проверяем активна ли подписка
    has_sub = user.subscription_end and user.subscription_end > now
    
    if not has_sub:
        if not user.is_trial_used:
            builder.row(InlineKeyboardButton(text="🎁 Попробовать бесплатно 24ч", callback_data="activate_trial"))
        builder.row(InlineKeyboardButton(text="💳 Купить подписку", callback_data="buy_subscription"))
    else:
        builder.row(InlineKeyboardButton(text="🚀 Зайти в закрытый канал", callback_data="get_channel_link"))
        
    builder.row(InlineKeyboardButton(text="💰 Кошелек", callback_data="wallet_main"))
    builder.row(InlineKeyboardButton(text="⚙️ Настройки и фильтры", callback_data="open_settings"))
    return builder.as_markup()

def get_channel_link_kb() -> InlineKeyboardMarkup:
    """Клавиатура для сообщения со ссылкой на закрытый канал"""
    return Kb_Helper.add_common_buttons(InlineKeyboardBuilder()).as_markup()
