from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram_i18n import LazyProxy
from aiogram_i18n.types import InlineKeyboardMarkup, InlineKeyboardButton
from src.bot.utils.kb_helper import Kb_Helper
from src.database.models import User
from src.database.functions import get_utc_now

toggle = Kb_Helper.toggle_icon

def get_admin_main_kb() -> InlineKeyboardMarkup:
    """Стартовая клавиатура админки"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-admin-analytics"), callback_data="admin_bi_main"))
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-admin-broadcast"), callback_data="admin_broadcast_start"))
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-admin-users"), callback_data="admin_page_1"))

    Kb_Helper.add_common_buttons(builder)
    return builder.as_markup()

def get_users_list_kb(
    users: list[User],
    page: int,
    total_pages: int,
    filter_status: str = "all",
    search_query: str | None = None,
) -> InlineKeyboardMarkup:
    """Клавиатура списка пользователей с пагинацией и фильтрами"""
    builder = InlineKeyboardBuilder()
    now = get_utc_now()

    # Верхний блок: Поиск и Фильтр
    filter_labels = {"all": "Все", "active": "С подпиской", "inactive": "Без подписки"}
    filter_text = f"🎭 Фильтр: {filter_labels.get(filter_status, '???')}"
    search_text = "🔍 Поиск" if not search_query else f"🔍: {search_query[:10]}..."

    builder.row(
        InlineKeyboardButton(text=search_text, callback_data="admin_user_search"),
        InlineKeyboardButton(text=filter_text, callback_data="admin_filter_toggle"),
    )

    # Кнопка сброса (если что-то активно)
    if filter_status != "all" or search_query:
        builder.row(
            InlineKeyboardButton(text="❌ Сбросить всё", callback_data="admin_search_reset")
        )

    for user in users:
        is_active = user.subscription_end and user.subscription_end > now
        emoji = "🟢" if is_active else "⚪"

        name = f"@{user.username}" if user.username else f"ID: {user.id}"
        date_str = user.created_at.strftime("%d.%m.%y")
        btn_text = f"{emoji} {name} | {date_str}"

        builder.row(
            InlineKeyboardButton(text=btn_text, callback_data=f"admin_user_{user.id}")
        )
        
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
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-admin-send-message"), callback_data=f"admin_send_msg:{user_id}"))

    Kb_Helper.add_common_buttons(builder)
    return builder.as_markup()

def get_cancel_fsm_kb() -> InlineKeyboardMarkup:
    """Кнопка отмены для FSM состояний"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-wallet-cancel"), callback_data="admin_fsm_stop"))
    return builder.as_markup()


def get_cancel_admin_action_kb() -> InlineKeyboardMarkup:
    """Кнопка отмены для персональных действий админа."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-wallet-cancel"), callback_data="cancel_admin_action"))
    return builder.as_markup()
