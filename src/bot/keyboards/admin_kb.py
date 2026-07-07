from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram_i18n import LazyProxy
from aiogram_i18n.types import InlineKeyboardMarkup, InlineKeyboardButton
from src.bot.utils.kb_helper import Kb_Helper
from src.database.models import User
from src.bot.utils.kb_helper import Kb_Helper

toggle = Kb_Helper.toggle_icon

def get_admin_main_kb() -> InlineKeyboardMarkup:
    """Стартовая клавиатура админки"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-admin-analytics"), callback_data="admin_bi_main"))
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-admin-broadcast"), callback_data="admin_broadcast_start"))
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-admin-channel-settings"), callback_data="admin_channel_settings"))
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-admin-users"), callback_data="admin_page_1"))

    Kb_Helper.add_common_buttons(builder)
    return builder.as_markup()

def get_users_list_kb(users: list[User], page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Клавиатура списка пользователей с пагинацией"""
    builder = InlineKeyboardBuilder()
    
    for user in users:
        name = f"@{user.username}" if user.username else f"ID: {user.id}"
        date_str = user.created_at.strftime("%d.%m.%y")
        btn_text = f"👤 {name} | {date_str}"
        
        builder.row(InlineKeyboardButton(text=btn_text, callback_data=f"admin_user_{user.id}"))
        
    # Блок пагинации (стрелки)
    nav_buttons = []
    
    # Кнопка НАЗАД
    if page > 1:
        nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"admin_page_{page-1}"))
    else:
        nav_buttons.append(InlineKeyboardButton(text=" ", callback_data="ignore"))
    # СЧЕТЧИК
    nav_buttons.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="ignore"))
    # Кнопка ВПЕРЕД
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"admin_page_{page+1}"))
    else:
        nav_buttons.append(InlineKeyboardButton(text=" ", callback_data="ignore"))
        
    builder.row(*nav_buttons)
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-admin-main-menu"), callback_data="admin_main"))
    
    return builder.as_markup()

def get_user_manage_kb(user_id: int, is_blocked: bool) -> InlineKeyboardMarkup:
    """Кнопки управления конкретным пользователем"""
    builder = InlineKeyboardBuilder()
    
    if is_blocked:
        builder.row(InlineKeyboardButton(text=LazyProxy("kb-admin-unblock"), callback_data=f"admin_toggle_{user_id}"))
    else:
        builder.row(InlineKeyboardButton(text=LazyProxy("kb-admin-block"), callback_data=f"admin_toggle_{user_id}"))

    builder.row(InlineKeyboardButton(text=LazyProxy("kb-admin-edit-subscription"), callback_data=f"admin_subs_{user_id}"))

    Kb_Helper.add_common_buttons(builder)
    return builder.as_markup()

def get_admin_channel_kb(settings) -> InlineKeyboardMarkup:
    """Клавиатура управления настройками канала"""
    builder = InlineKeyboardBuilder()

    status_btn = LazyProxy("kb-admin-channel-posting-on") if settings.is_active else LazyProxy("kb-admin-channel-posting-off")
    builder.row(InlineKeyboardButton(text=status_btn, callback_data="admin_chan_toggle_active"))

    mode_label = LazyProxy("kb-settings-mode-percent") if settings.threshold_mode == "PERCENT" else LazyProxy("kb-settings-mode-usd")
    builder.row(
        InlineKeyboardButton(text=LazyProxy("kb-settings-mode", mode_label=mode_label), callback_data="admin_chan_toggle_threshold_mode"))

    # Кнопки порогов
    if settings.threshold_mode == "PERCENT":
        builder.row(
            InlineKeyboardButton(text=LazyProxy("kb-settings-threshold-volume-percent"), callback_data="admin_chan_set_mcap_pct"),
            InlineKeyboardButton(text=LazyProxy("kb-settings-threshold-cascade-percent"), callback_data="admin_chan_set_mcap_cas_pct"))
        builder.row(
            InlineKeyboardButton(text=LazyProxy("kb-settings-threshold-min-usd"), callback_data="admin_chan_set_mcap_min_usd"),
            InlineKeyboardButton(text=LazyProxy("kb-settings-threshold-cascade-min-usd"), callback_data="admin_chan_set_mcap_cas_min_usd"))
    else:
        builder.row(
            InlineKeyboardButton(text=LazyProxy("kb-settings-threshold-volume-usd"), callback_data="admin_chan_set_threshold"),
            InlineKeyboardButton(text=LazyProxy("kb-settings-threshold-cascade-usd"), callback_data="admin_chan_set_cascade_threshold"))

    # Тумблеры сигналов
    builder.row(
        InlineKeyboardButton(text=LazyProxy("kb-settings-toggle-cascade", status=toggle(settings.alert_cascade)), callback_data="admin_chan_toggle_cascade"),
        InlineKeyboardButton(text=LazyProxy("kb-settings-toggle-volume", status=toggle(settings.alert_volume)), callback_data="admin_chan_toggle_volume"),
        InlineKeyboardButton(text=LazyProxy("kb-settings-toggle-squeeze", status=toggle(settings.alert_squeeze)), callback_data="admin_chan_toggle_squeeze"))

    # Тумблеры направлений
    builder.row(
        InlineKeyboardButton(text=LazyProxy("kb-settings-toggle-longs", status=toggle(settings.alert_longs)), callback_data="admin_chan_toggle_longs"),
        InlineKeyboardButton(text=LazyProxy("kb-settings-toggle-shorts", status=toggle(settings.alert_shorts)), callback_data="admin_chan_toggle_shorts"))

    # Тумблеры аналитики
    builder.row(
        InlineKeyboardButton(text=LazyProxy("kb-settings-toggle-oi", status=toggle(settings.alert_oi)), callback_data="admin_chan_toggle_oi"),
        InlineKeyboardButton(text=LazyProxy("kb-settings-toggle-rsi", status=toggle(settings.alert_rsi)), callback_data="admin_chan_toggle_rsi"),
        InlineKeyboardButton(text=LazyProxy("kb-settings-toggle-cvd", status=toggle(settings.alert_cvd)), callback_data="admin_chan_toggle_cvd"))

    builder.row(
        InlineKeyboardButton(text=LazyProxy("kb-admin-channel-oi-thresholds"), callback_data="admin_chan_set_oi"))

    builder.row(InlineKeyboardButton(text=LazyProxy("kb-admin-channel-restart-dashboard"), callback_data="admin_chan_restart_dash"))

    builder.row(InlineKeyboardButton(text=LazyProxy("kb-common-back"), callback_data="admin_main"))
    return builder.as_markup()

def get_cancel_fsm_kb() -> InlineKeyboardMarkup:
    """Кнопка отмены для FSM состояний"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-wallet-cancel"), callback_data="admin_fsm_stop"))
    return builder.as_markup()
