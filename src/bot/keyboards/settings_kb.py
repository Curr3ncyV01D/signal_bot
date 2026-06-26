from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from src.database.models import User

def get_settings_kb(user: User) -> InlineKeyboardMarkup:
    """Клавиатура настроек"""
    builder = InlineKeyboardBuilder()

    cas = "✅" if user.alert_cascade else "❌"
    vol = "✅" if user.alert_volume else "❌"
    sqz = "✅" if user.alert_squeeze else "❌"
    
    long_direction = "✅" if user.alert_longs else "❌"
    short_direction = "✅" if user.alert_shorts else "❌"
    
    mode_label = "% MCAP 💎" if user.threshold_mode == "PERCENT" else "USD 💵"
    
    oi_mode = "✅" if user.alert_oi else "❌"
    rsi_mode = "✅" if user.alert_rsi else "❌"
    cvd_mode = "✅" if user.alert_cvd else "❌"

    # --- БЛОК ЛИКВИДАЦИЙ ---
    builder.row(InlineKeyboardButton(text="-- ❓ Справка: ЛИКВИДАЦИИ --", callback_data="help_liq"))
    
    # Тумблер режима
    builder.row(
        InlineKeyboardButton(text=f"⚙️ Режим: {mode_label}", callback_data="toggle_threshold_mode")
    )

    # Кнопки порогов
    if user.threshold_mode == "PERCENT":
        builder.row(
            InlineKeyboardButton(text="💰 Порог объема (%)", callback_data="set_mcap_pct"),
            InlineKeyboardButton(text="⚡ Порог каскада (%)", callback_data="set_mcap_cas_pct")
        )
        builder.row(
            InlineKeyboardButton(text="Мин. порог ($)", callback_data="set_mcap_min_usd"),
            InlineKeyboardButton(text="Мин. порог каскада ($)", callback_data="set_mcap_cas_min_usd")
        )
    else:
        builder.row(
            InlineKeyboardButton(text="💰 Порог объема ($)", callback_data="set_threshold"),
            InlineKeyboardButton(text="⚡ Порог каскада ($)", callback_data="set_cascade_threshold")
        )

    # Тублеры сигналов
    builder.row(
        InlineKeyboardButton(text=f"{cas} Каскад", callback_data="toggle_cascade"),
        InlineKeyboardButton(text=f"{vol} Объем", callback_data="toggle_volume"),
        InlineKeyboardButton(text=f"{sqz} Сквиз", callback_data="toggle_squeeze")
    )

    # Тумблеры направлений
    builder.row(
        InlineKeyboardButton(text=f"🟢 LONG: {long_direction}", callback_data="toggle_longs"),
        InlineKeyboardButton(text=f"🔴 SHORT: {short_direction}", callback_data="toggle_shorts")
    )

    # --- БЛОК АНАЛИТИКИ ---
    builder.row(InlineKeyboardButton(text="-- ❓ Справка: АНАЛИТИКА  --", callback_data="help_analytics"))
    
    # Тумблеры аналитики
    builder.row(
        InlineKeyboardButton(text=f"{oi_mode} OI", callback_data="toggle_oi"),
        InlineKeyboardButton(text=f"{rsi_mode} RSI", callback_data="toggle_rsi"),
        InlineKeyboardButton(text=f"{cvd_mode} CVD", callback_data="toggle_cvd")
    )
    
    # Пороги ОИ
    builder.row(
        InlineKeyboardButton(text="⚙️ Пороги ОИ (% и $)", callback_data="menu_oi_thresholds")
    )
    
    builder.row(InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="back_to_main"))
    return builder.as_markup()

def get_back_to_settings_kb() -> InlineKeyboardMarkup:
    """Клавиатура для возврата из справки обратно в настройки"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⬅️ Назад к настройкам", callback_data="back_to_settings"))
    return builder.as_markup()
