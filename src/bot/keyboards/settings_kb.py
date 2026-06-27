from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from src.database.models import User
from src.bot.utils.kb_helper import Kb_Helper

toggle = Kb_Helper.toggle_icon

def get_settings_kb(user: User) -> InlineKeyboardMarkup:
    """Клавиатура настроек"""
    builder = InlineKeyboardBuilder()

    mode_label = "% MCAP 💎" if user.threshold_mode == "PERCENT" else "USD 💵"
    
    # --- БЛОК ЛИКВИДАЦИЙ ---
    builder.row(InlineKeyboardButton(text="-- ❓ Справка: ЛИКВИДАЦИИ --", callback_data="help_liq"))
    # Тумблер режима
    builder.row(
        InlineKeyboardButton(text=f"⚙️ Режим: {mode_label}", callback_data="toggle_threshold_mode"))
    # Кнопки порогов
    if user.threshold_mode == "PERCENT":
        builder.row(
            InlineKeyboardButton(text="💰 Порог объема (%)", callback_data="set_mcap_pct"),
            InlineKeyboardButton(text="⚡ Порог каскада (%)", callback_data="set_mcap_cas_pct"))
        builder.row(
            InlineKeyboardButton(text="Мин. порог ($)", callback_data="set_mcap_min_usd"),
            InlineKeyboardButton(text="Мин. порог каскада ($)", callback_data="set_mcap_cas_min_usd"))
    else:
        builder.row(
            InlineKeyboardButton(text="💰 Порог объема ($)", callback_data="set_threshold"),
            InlineKeyboardButton(text="⚡ Порог каскада ($)", callback_data="set_cascade_threshold"))

    # Тублеры сигналов
    builder.row(
        InlineKeyboardButton(text=f"{toggle(user.alert_cascade)} Каскад", callback_data="toggle_cascade"),
        InlineKeyboardButton(text=f"{toggle(user.alert_volume)} Объем", callback_data="toggle_volume"),
        InlineKeyboardButton(text=f"{toggle(user.alert_squeeze)} Сквиз", callback_data="toggle_squeeze"))
        
    # Тумблеры направлений
    builder.row(
        InlineKeyboardButton(text=f"🟢 LONG: {toggle(user.alert_longs)}", callback_data="toggle_longs"),
        InlineKeyboardButton(text=f"🔴 SHORT: {toggle(user.alert_shorts)}", callback_data="toggle_shorts"))

    # --- БЛОК АНАЛИТИКИ ---
    builder.row(InlineKeyboardButton(text="-- ❓ Справка: АНАЛИТИКА  --", callback_data="help_analytics"))
    # Тумблеры аналитики
    builder.row(
        InlineKeyboardButton(text=f"{toggle(user.alert_oi)} OI", callback_data="toggle_oi"),
        InlineKeyboardButton(text=f"{toggle(user.alert_rsi)} RSI", callback_data="toggle_rsi"),
        InlineKeyboardButton(text=f"{toggle(user.alert_cvd)} CVD", callback_data="toggle_cvd"))
    # Пороги ОИ
    builder.row(
        InlineKeyboardButton(text="⚙️ Пороги ОИ (% и $)", callback_data="menu_oi_thresholds"))
    
    builder.row(InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="back_to_main"))
    return builder.as_markup()

def get_back_to_settings_kb() -> InlineKeyboardMarkup:
    """Клавиатура для возврата из справки обратно в настройки"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⬅️ Назад к настройкам", callback_data="back_to_settings"))
    return builder.as_markup()
