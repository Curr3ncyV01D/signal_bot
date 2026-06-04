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
        # Здесь в Этапе 4 появится кнопка "💳 Купить подписку"
    else:
        builder.row(InlineKeyboardButton(text="🚀 Зайти в закрытый канал", callback_data="get_channel_link"))
        
    builder.row(InlineKeyboardButton(text="⚙️ Настройки и фильтры", callback_data="open_settings"))
    return builder.as_markup()

def get_channel_link_kb() -> InlineKeyboardMarkup:
    """Клавиатура для получения ссылки на закрытый канал"""
    return Kb_Helper.add_common_buttons(InlineKeyboardBuilder()).as_markup()


def get_settings_kb(user: User) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    # Статус ликвидаций (Stage 1)
    cas = "✅" if user.alert_cascade else "❌"
    vol = "✅" if user.alert_volume else "❌"
    sqz = "✅" if user.alert_squeeze else "❌"
    
    # Статус аналитики (Stage 2)
    oi_btn = "✅" if user.alert_oi else "❌"
    rsi_btn = "✅" if user.alert_rsi else "❌"
    cvd_btn = "✅" if user.alert_cvd else "❌"

    # --- БЛОК ЛИКВИДАЦИЙ ---
    builder.row(InlineKeyboardButton(text="-- ❓ Справка: ЛИКВИДАЦИИ --", callback_data="help_liq"))
    
    # Тумблеры ликвидаций (в один ряд)
    builder.row(
        InlineKeyboardButton(text=f"{cas} Каскады", callback_data="toggle_cascade"),
        InlineKeyboardButton(text=f"{vol} Объем", callback_data="toggle_volume"),
        InlineKeyboardButton(text=f"{sqz} Сквиз", callback_data="toggle_squeeze")
    )
    
    # Кнопки порогов ликвидаций
    builder.row(
        InlineKeyboardButton(text="💰 Порог объема ($)", callback_data="set_threshold"),
        InlineKeyboardButton(text="⚡ Порог каскада ($)", callback_data="set_cascade_threshold")
    )

    # --- БЛОК АНАЛИТИКИ ---
    builder.row(InlineKeyboardButton(text="-- ❓ Справка: АНАЛИТИКА  --", callback_data="help_analytics"))
    
    # Тумблеры аналитики (в один ряд)
    builder.row(
        InlineKeyboardButton(text=f"{oi_btn} OI", callback_data="toggle_oi"),
        InlineKeyboardButton(text=f"{rsi_btn} RSI", callback_data="toggle_rsi"),
        InlineKeyboardButton(text=f"{cvd_btn} CVD", callback_data="toggle_cvd")
    )
    
    # Пороги аналитики (ОИ)
    builder.row(
        InlineKeyboardButton(text="⚙️ Пороги ОИ (% и $)", callback_data="menu_oi_thresholds")
    )
    
    # Кнопка возврата в главное меню
    builder.row(InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="back_to_main"))

    return builder.as_markup()

def get_back_to_settings_kb() -> InlineKeyboardMarkup:
    """Клавиатура для возврата из справки обратно в настройки"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⬅️ Назад к настройкам", callback_data="back_to_settings"))
    return builder.as_markup()