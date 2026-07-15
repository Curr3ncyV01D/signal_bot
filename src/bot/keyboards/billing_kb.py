from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram_i18n import LazyProxy
from aiogram_i18n.types import InlineKeyboardMarkup, InlineKeyboardButton
from src.core.config import config
from src.core.localization import normalize_locale_code
from src.database.models import User

def get_wallet_main_kb(
    user: User,
    *,
    renew_button_key: str = "kb-wallet-renew",
) -> InlineKeyboardMarkup:
    """Главное меню кошелька"""
    builder = InlineKeyboardBuilder()

    builder.row(InlineKeyboardButton(text=LazyProxy(renew_button_key), callback_data="buy_subscription"))
    auto_renewal_text = LazyProxy("kb-wallet-autorenew-on") if user.auto_renewal else LazyProxy("kb-wallet-autorenew-off")
    builder.row(InlineKeyboardButton(text=auto_renewal_text, callback_data="toggle_auto_renewal"))
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-wallet-history"), callback_data="tx_history"))
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-wallet-back-main"), callback_data="back_to_main"))
    return builder.as_markup()


def get_manual_payment_kb(
    external_id: str,
    *,
    screenshot_button_key: str = "kb-wallet-send-screenshot",
) -> InlineKeyboardMarkup:
    """Клавиатура ручной оплаты со скриншотом."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=LazyProxy(screenshot_button_key),
            callback_data=f"manual_upload_{external_id}",
        )
    )
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-wallet-cancel"), callback_data="buy_subscription"))
    return builder.as_markup()


def get_payment_success_kb() -> InlineKeyboardMarkup:
    """Клавиатура для успешной оплаты с возвратом в главное меню."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=LazyProxy("main-button-home"), callback_data="back_to_main"))
    return builder.as_markup()

def get_wallet_back_kb(back_callback: str = "wallet_main") -> InlineKeyboardMarkup:
    """Кнопка возврата на предыдущий уровень меню."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-common-back"), callback_data=back_callback))
    return builder.as_markup()


def get_profile_main_kb(user: User) -> InlineKeyboardMarkup:
    """Меню личного кабинета."""
    builder = InlineKeyboardBuilder()
    language_code = normalize_locale_code(user.language_code)

    language_button = (
        LazyProxy("kb-wallet-language-ru")
        if language_code == "ru"
        else LazyProxy("kb-wallet-language-en")
    )
    builder.row(InlineKeyboardButton(text=language_button, callback_data="profile_change_language"))

    builder.row(InlineKeyboardButton(text=LazyProxy("kb-wallet-partner"), callback_data="profile_partner_cabinet"))
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-wallet-back-main"), callback_data="back_to_main"))
    return builder.as_markup()

def get_subscription_tariffs_kb(back_callback: str = "wallet_main") -> InlineKeyboardMarkup:
    """Список тарифов для покупки"""
    builder = InlineKeyboardBuilder()
    for days, price in config.TARIFFS.items():
        builder.row(InlineKeyboardButton(
            text=LazyProxy("kb-wallet-plan-price", days=days, price=price), 
            callback_data=f"buy_plan_{days}"
        ))
    
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-main-support"), url=config.SUPPORT_URL))
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-common-back"), callback_data=back_callback))
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
