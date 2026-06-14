from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_bi_main_kb() -> InlineKeyboardMarkup:
    """Главное меню BI-аналитики"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💰 Финансы", callback_data="admin_bi_finance"))
    builder.row(InlineKeyboardButton(text="👥 Аудитория", callback_data="admin_bi_audience"))
    builder.row(InlineKeyboardButton(text="⚙️ Система", callback_data="admin_bi_system"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад в админку", callback_data="admin_main"))
    return builder.as_markup()

def get_bi_finance_kb() -> InlineKeyboardMarkup:
    """Клавиатура блока финансов"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_bi_finance"))
    builder.row(InlineKeyboardButton(text="📄 Выгрузить .csv", callback_data="admin_bi_export_csv"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_bi_main"))
    return builder.as_markup()

def get_bi_audience_kb() -> InlineKeyboardMarkup:
    """Клавиатура блока аудитории"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_bi_audience"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_bi_main"))
    return builder.as_markup()

def get_bi_system_kb() -> InlineKeyboardMarkup:
    """Клавиатура технического блока"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_bi_system"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_bi_main"))
    return builder.as_markup()
