from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram_i18n import LazyProxy
from aiogram_i18n.types import InlineKeyboardButton, InlineKeyboardMarkup
from src.core.config import config
from src.database.models import User
from src.bot.utils.kb_helper import Kb_Helper

toggle = Kb_Helper.toggle_icon

def get_settings_kb(user: User) -> InlineKeyboardMarkup:
    """Клавиатура настроек"""
    builder = InlineKeyboardBuilder()
  
    # --- БЛОК ЛИКВИДАЦИЙ ---
    builder.row(
        InlineKeyboardButton(text=LazyProxy("kb-settings-help-liq"), callback_data="help_liq"))
    # Тумблер режима
    builder.row(
        InlineKeyboardButton(text=LazyProxy("kb-settings-mode", mode=user.threshold_mode), callback_data="toggle_threshold_mode"))
    # Кнопки порогов
    if user.threshold_mode == "PERCENT":
        builder.row(
            InlineKeyboardButton(text=LazyProxy("kb-settings-threshold-volume-percent"), callback_data="set_mcap_pct"),
            InlineKeyboardButton(text=LazyProxy("kb-settings-threshold-cascade-percent"), callback_data="set_mcap_cas_pct"))
        builder.row(
            InlineKeyboardButton(text=LazyProxy("kb-settings-threshold-min-usd"), callback_data="set_mcap_min_usd"),
            InlineKeyboardButton(text=LazyProxy("kb-settings-threshold-cascade-min-usd"), callback_data="set_mcap_cas_min_usd"))
    else:
        builder.row(
            InlineKeyboardButton(text=LazyProxy("kb-settings-threshold-volume-usd"), callback_data="set_threshold"),
            InlineKeyboardButton(text=LazyProxy("kb-settings-threshold-cascade-usd"), callback_data="set_cascade_threshold"))

    # Тублеры сигналов
    builder.row(
        InlineKeyboardButton(text=LazyProxy("kb-settings-toggle-cascade", status=toggle(user.alert_cascade)), callback_data="toggle_cascade"),
        InlineKeyboardButton(text=LazyProxy("kb-settings-toggle-volume", status=toggle(user.alert_volume)), callback_data="toggle_volume"),
        InlineKeyboardButton(text=LazyProxy("kb-settings-toggle-squeeze", status=toggle(user.alert_squeeze)), callback_data="toggle_squeeze"))
        
    # Тумблеры направлений
    builder.row(
        InlineKeyboardButton(text=LazyProxy("kb-settings-toggle-longs", status=toggle(user.alert_longs)), callback_data="toggle_longs"),
        InlineKeyboardButton(text=LazyProxy("kb-settings-toggle-shorts", status=toggle(user.alert_shorts)), callback_data="toggle_shorts"))

    # --- БЛОК АНАЛИТИКИ ---
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-settings-help-analytics"), callback_data="help_analytics"))
    # Тумблеры аналитики
    builder.row(
        InlineKeyboardButton(text=LazyProxy("kb-settings-toggle-oi", status=toggle(user.alert_oi)), callback_data="toggle_oi"),
        InlineKeyboardButton(text=LazyProxy("kb-settings-toggle-rsi", status=toggle(user.alert_rsi)), callback_data="toggle_rsi"),
        InlineKeyboardButton(text=LazyProxy("kb-settings-toggle-cvd", status=toggle(user.alert_cvd)), callback_data="toggle_cvd"))
    # Пороги ОИ
    builder.row(
        InlineKeyboardButton(text=LazyProxy("kb-settings-oi-thresholds"), callback_data="menu_oi_thresholds"))
    
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-settings-back-main"), callback_data="back_to_main"))
    return builder.as_markup()

def get_back_to_settings_kb() -> InlineKeyboardMarkup:
    """Клавиатура для возврата из справки обратно в настройки"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-settings-ask-question"), url=config.SUPPORT_URL))
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-settings-back"), callback_data="back_to_settings"))
    return builder.as_markup()
