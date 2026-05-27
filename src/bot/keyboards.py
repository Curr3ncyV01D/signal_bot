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
    builder.row(InlineKeyboardButton(text="--- ЛИКВИДАЦИИ ---", callback_data="ignore"))
    
    # Тумблеры ликвидаций (в один ряд)
    builder.row(
        InlineKeyboardButton(text=f"{cas} Каскады", callback_data="toggle_cascade"),
        InlineKeyboardButton(text=f"{vol} Объем", callback_data="toggle_volume"),
        InlineKeyboardButton(text=f"{sqz} Сквиз", callback_data="toggle_squeeze")
    )
    
    # Кнопки порогов ликвидаций (вернули на место!)
    builder.row(
        InlineKeyboardButton(text="💰 Порог объема ($)", callback_data="set_threshold"),
        InlineKeyboardButton(text="⚡ Порог каскада ($)", callback_data="set_cascade_threshold")
    )

    # --- БЛОК АНАЛИТИКИ ---
    builder.row(InlineKeyboardButton(text="--- АНАЛИТИКА ---", callback_data="ignore"))
    
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
    
    # Кнопка закрытия
    builder.row(InlineKeyboardButton(text="⬅️ Закрыть", callback_data="close_message"))

    return builder.as_markup()