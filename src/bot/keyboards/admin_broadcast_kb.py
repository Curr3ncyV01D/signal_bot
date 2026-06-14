from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_segment_selection_kb() -> InlineKeyboardMarkup:
    """Клавиатура выбора сегмента аудитории"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="👥 Всем", callback_data="broadcast_segment_all"))
    builder.row(InlineKeyboardButton(text="💎 Только с подпиской", callback_data="broadcast_segment_vip"))
    builder.row(InlineKeyboardButton(text="🆓 Только без подписки", callback_data="broadcast_segment_free"))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="broadcast_cancel"))
    return builder.as_markup()

def get_broadcast_confirm_kb() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения запуска рассылки"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🚀 Запустить рассылку", callback_data="broadcast_confirm_start"))
    builder.row(InlineKeyboardButton(text="🔄 Изменить / Отмена", callback_data="broadcast_cancel"))
    return builder.as_markup()
