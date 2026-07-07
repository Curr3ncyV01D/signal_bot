from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram_i18n import LazyProxy
from aiogram_i18n.types import InlineKeyboardMarkup, InlineKeyboardButton
from src.core.config import config
from src.core.localization import normalize_locale_code
from src.database.models import User

def get_wallet_main_kb(user: User) -> InlineKeyboardMarkup:
    """Главное меню кошелька"""
    builder = InlineKeyboardBuilder()
    language_code = normalize_locale_code(user.language_code)

    builder.row(InlineKeyboardButton(text=LazyProxy("kb-wallet-renew"), callback_data="buy_subscription"))
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-wallet-deposit"), callback_data="deposit"))
    auto_renewal_text = LazyProxy("kb-wallet-autorenew-on") if user.auto_renewal else LazyProxy("kb-wallet-autorenew-off")
    builder.row(InlineKeyboardButton(text=auto_renewal_text, callback_data="toggle_auto_renewal"))
    language_button = (
        LazyProxy("kb-wallet-language-ru")
        if language_code == "ru"
        else LazyProxy("kb-wallet-language-en")
    )
    builder.row(InlineKeyboardButton(text=language_button, callback_data="change_language"))
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-wallet-partner"), callback_data="partner_cabinet"))
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-wallet-history"), callback_data="tx_history"))
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-wallet-back-main"), callback_data="back_to_main"))
    return builder.as_markup()

def get_deposit_amounts_kb() -> InlineKeyboardMarkup:
    """Выбор суммы пополнения"""
    builder = InlineKeyboardBuilder()
    # Используем цены из тарифов как пресеты
    for days, price in config.TARIFFS.items():
        builder.button(text=f"{price} USDT", callback_data=f"deposit_{price}")
    
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-common-back"), callback_data="wallet_main"))
    return builder.as_markup()

def get_payment_link_kb(url: str, invoice_id: int) -> InlineKeyboardMarkup:
    """Ссылка на оплату и кнопка проверки"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-wallet-pay-cryptobot"), url=url))
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-wallet-check-payment"), callback_data=f"check_pay_{invoice_id}"))
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-wallet-payment-issue"), url=config.SUPPORT_URL))
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-common-back"), callback_data="deposit"))
    return builder.as_markup()

def get_wallet_back_kb() -> InlineKeyboardMarkup:
    """Кнопка возврата в главное меню кошелька."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-common-back"), callback_data="wallet_main"))
    return builder.as_markup()

def get_subscription_tariffs_kb() -> InlineKeyboardMarkup:
    """Список тарифов для покупки"""
    builder = InlineKeyboardBuilder()
    for days, price in config.TARIFFS.items():
        # Передаем только сырые данные (days и price). 
        # Никаких вложенных LazyProxy!
        builder.row(InlineKeyboardButton(
            text=LazyProxy("kb-wallet-plan-price", days=days, price=price), 
            callback_data=f"buy_plan_{days}"
        ))
    
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-main-support"), url=config.SUPPORT_URL))
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-common-back"), callback_data="wallet_main"))
    return builder.as_markup()

def get_balance_purchase_confirm_kb(days: int) -> InlineKeyboardMarkup:
    """Подтверждение покупки подписки с баланса."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=LazyProxy("kb-wallet-confirm-debit"),
            callback_data=f"confirm_balance_purchase_{days}"
        )
    )
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-wallet-cancel"), callback_data="cancel_balance_purchase"))
    return builder.as_markup()
