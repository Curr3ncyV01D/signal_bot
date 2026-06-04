from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_status_kb() -> InlineKeyboardMarkup:
    """Клавиатура для сообщения со статусом системы"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔄 Обновить статус", callback_data="refresh_status"))
    return builder.as_markup()