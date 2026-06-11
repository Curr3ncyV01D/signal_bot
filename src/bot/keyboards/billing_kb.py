from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from src.core.config import config

def get_wallet_main_kb(balance: float) -> InlineKeyboardMarkup:
    """Главное меню кошелька"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Пополнить баланс", callback_data="deposit"))
    builder.row(InlineKeyboardButton(text="💎 Купить подписку", callback_data="buy_subscription"))
    builder.row(InlineKeyboardButton(text="📜 История транзакций", callback_data="tx_history"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="back_to_main"))
    return builder.as_markup()

def get_deposit_amounts_kb() -> InlineKeyboardMarkup:
    """Выбор суммы пополнения"""
    builder = InlineKeyboardBuilder()
    # Используем цены из тарифов как пресеты
    for days, price in config.TARIFFS.items():
        builder.button(text=f"{price} USDT", callback_data=f"deposit_{price}")
    
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="wallet_main"))
    return builder.as_markup()

def get_payment_link_kb(url: str, invoice_id: int) -> InlineKeyboardMarkup:
    """Ссылка на оплату и кнопка проверки"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔗 Оплатить (CryptoBot)", url=url))
    builder.row(InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_pay_{invoice_id}"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="deposit"))
    return builder.as_markup()

def get_subscription_tariffs_kb() -> InlineKeyboardMarkup:
    """Список тарифов для покупки"""
    builder = InlineKeyboardBuilder()
    for days, price in config.TARIFFS.items():
        # Универсальное форматирование лейбла
        if days % 30 == 0:
            months = days // 30
            if months == 1: label = "1 месяц"
            elif 2 <= months <= 4: label = f"{months} месяца"
            else: label = f"{months} месяцев"
        else:
            label = f"{days} дней"
        
        builder.row(InlineKeyboardButton(
            text=f"{label} — {price} USDT", 
            callback_data=f"buy_plan_{days}"
        ))
    
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="wallet_main"))
    return builder.as_markup()
