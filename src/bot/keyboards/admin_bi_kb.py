from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram_i18n import LazyProxy
from aiogram_i18n.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_bi_main_kb() -> InlineKeyboardMarkup:
    """Главное меню BI-аналитики"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-admin-bi-finance"), callback_data="admin_bi_finance"))
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-admin-bi-audience"), callback_data="admin_bi_audience"))
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-admin-bi-system"), callback_data="admin_bi_system"))
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-admin-bi-back-admin"), callback_data="admin_main"))
    return builder.as_markup()

def get_bi_finance_kb() -> InlineKeyboardMarkup:
    """Клавиатура блока финансов"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-admin-refresh"), callback_data="admin_bi_finance"))
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-admin-bi-export-csv"), callback_data="admin_bi_export_csv"))
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-common-back"), callback_data="admin_bi_main"))
    return builder.as_markup()

def get_bi_audience_kb() -> InlineKeyboardMarkup:
    """Клавиатура блока аудитории"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-admin-refresh"), callback_data="admin_bi_audience"))
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-common-back"), callback_data="admin_bi_main"))
    return builder.as_markup()

def get_bi_system_kb() -> InlineKeyboardMarkup:
    """Клавиатура технического блока"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-admin-refresh"), callback_data="admin_bi_system"))
    builder.row(
        InlineKeyboardButton(text=LazyProxy("kb-admin-bi-find-coin"), callback_data="admin_bi_symbol_search"),
        InlineKeyboardButton(text=LazyProxy("kb-admin-bi-export-txt"), callback_data="admin_bi_symbol_export")
    )
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-common-back"), callback_data="admin_bi_main"))
    return builder.as_markup()
