from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from src.bot.utils.kb_helper import Kb_Helper
from src.database.models import User

def get_admin_main_kb() -> InlineKeyboardMarkup:
    """Стартовая клавиатура админки"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="👥 Список пользователей", callback_data="admin_page_1"))

    Kb_Helper.add_common_buttons(builder)

    return builder.as_markup()

def get_users_list_kb(users: list[User], page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Клавиатура списка пользователей с пагинацией"""
    builder = InlineKeyboardBuilder()
    
    # Кнопки пользователей (по одной в ряд)
    for user in users:
        # Если нет юзернейма, показываем ID
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
        nav_buttons.append(InlineKeyboardButton(text=" ", callback_data="ignore")) # Пустышка для ровного ряда
        
    # СЧЕТЧИК
    nav_buttons.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="ignore"))
    
    # Кнопка ВПЕРЕД
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"admin_page_{page+1}"))
    else:
        nav_buttons.append(InlineKeyboardButton(text=" ", callback_data="ignore"))
        
    builder.row(*nav_buttons)
    builder.row(InlineKeyboardButton(text="🔙 В главное меню", callback_data="admin_main"))
    
    return builder.as_markup()

def get_user_manage_kb(user_id: int, is_blocked: bool) -> InlineKeyboardMarkup:
    """Кнопки управления конкретным пользователем"""
    builder = InlineKeyboardBuilder()
    if is_blocked:
        builder.row(InlineKeyboardButton(text="✅ Разблокировать", callback_data=f"admin_toggle_{user_id}"))
    else:
        builder.row(InlineKeyboardButton(text="🛑 Заблокировать", callback_data=f"admin_toggle_{user_id}"))

    Kb_Helper.add_common_buttons(builder)
    
    return builder.as_markup()