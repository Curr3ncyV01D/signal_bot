from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram_i18n import LazyProxy
from aiogram_i18n.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_segment_selection_kb() -> InlineKeyboardMarkup:
    """Клавиатура выбора сегмента аудитории"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-admin-broadcast-all"), callback_data="broadcast_segment_all"))
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-admin-broadcast-vip"), callback_data="broadcast_segment_vip"))
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-admin-broadcast-free"), callback_data="broadcast_segment_free"))
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-wallet-cancel"), callback_data="broadcast_cancel"))
    return builder.as_markup()

def get_broadcast_confirm_kb() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения запуска рассылки"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-admin-broadcast-start"), callback_data="broadcast_confirm_start"))
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-admin-broadcast-change-cancel"), callback_data="broadcast_cancel"))
    return builder.as_markup()
