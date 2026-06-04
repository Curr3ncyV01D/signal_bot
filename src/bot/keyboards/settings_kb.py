from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from src.database.models import User

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
