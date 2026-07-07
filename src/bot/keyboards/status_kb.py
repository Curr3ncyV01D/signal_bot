from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram_i18n import LazyProxy
from aiogram_i18n.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_status_kb() -> InlineKeyboardMarkup:
    """Клавиатура для сообщения со статусом системы"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-status-refresh"), callback_data="refresh_status"))
    return builder.as_markup()
