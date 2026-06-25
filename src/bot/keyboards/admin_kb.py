from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from src.bot.utils.kb_helper import Kb_Helper
from src.database.models import User

def get_admin_main_kb() -> InlineKeyboardMarkup:
    """Стартовая клавиатура админки"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📊 Аналитика и метрики", callback_data="admin_bi_main"))
    builder.row(InlineKeyboardButton(text="📣 Создать рассылку", callback_data="admin_broadcast_start"))
    builder.row(InlineKeyboardButton(text="📢 Настройки канала", callback_data="admin_channel_settings"))
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
    
    # Первая строка: Блокировка
    if is_blocked:
        builder.row(InlineKeyboardButton(text="✅ Разблокировать", callback_data=f"admin_toggle_{user_id}"))
    else:
        builder.row(InlineKeyboardButton(text="🛑 Заблокировать", callback_data=f"admin_toggle_{user_id}"))

    # Вторая строка: Управление подпиской
    builder.row(InlineKeyboardButton(text="📅 Изменить подписку", callback_data=f"admin_subs_{user_id}"))

    Kb_Helper.add_common_buttons(builder)
    
    return builder.as_markup()

def get_admin_channel_kb(settings) -> InlineKeyboardMarkup:
    """Клавиатура управления настройками канала"""
    builder = InlineKeyboardBuilder()
    
    # Главный тумблер
    status_btn = "🟢 Постинг ВКЛЮЧЕН" if settings.is_active else "🔴 Постинг ВЫКЛЮЧЕН"
    builder.row(InlineKeyboardButton(text=status_btn, callback_data="admin_chan_toggle_active"))

    # Тумблеры ликвидаций
    cas = "✅" if settings.alert_cascade else "❌"
    vol = "✅" if settings.alert_volume else "❌"
    sqz = "✅" if settings.alert_squeeze else "❌"

    # Направления
    lng = "✅" if settings.alert_longs else "❌"
    sht = "✅" if settings.alert_shorts else "❌"
    
    # Тумблеры направлений
    builder.row(
        InlineKeyboardButton(text=f"🟢 LONG: {lng}", callback_data="admin_chan_toggle_longs"),
        InlineKeyboardButton(text=f"🔴 SHORT: {sht}", callback_data="admin_chan_toggle_shorts")
    )

    builder.row(
        InlineKeyboardButton(text=f"{cas} Каскад", callback_data="admin_chan_toggle_cascade"),
        InlineKeyboardButton(text=f"{vol} Объем", callback_data="admin_chan_toggle_volume"),
        InlineKeyboardButton(text=f"{sqz} Сквиз", callback_data="admin_chan_toggle_squeeze")
    )

    # Тумблеры аналитики
    oi = "✅" if settings.alert_oi else "❌"
    rsi = "✅" if settings.alert_rsi else "❌"
    cvd = "✅" if settings.alert_cvd else "❌"
    builder.row(
        InlineKeyboardButton(text=f"{oi} OI", callback_data="admin_chan_toggle_oi"),
        InlineKeyboardButton(text=f"{rsi} RSI", callback_data="admin_chan_toggle_rsi"),
        InlineKeyboardButton(text=f"{cvd} CVD", callback_data="admin_chan_toggle_cvd")
    )

    # Пороги
    builder.row(
        InlineKeyboardButton(text="💰 Порог объема ($)", callback_data="admin_chan_set_vol"),
        InlineKeyboardButton(text="⚡ Порог каскада ($)", callback_data="admin_chan_set_cas")
    )
    builder.row(
        InlineKeyboardButton(text="⚙️ Пороги OI (% и $)", callback_data="admin_chan_set_oi")
    )

    # Управление дэшбордом
    builder.row(InlineKeyboardButton(text="🔄 Перезапустить Дэшборд", callback_data="admin_chan_restart_dash"))
    
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_main"))
    return builder.as_markup()

def get_cancel_fsm_kb() -> InlineKeyboardMarkup:
    """Кнопка отмены для FSM состояний"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="admin_fsm_stop"))
    return builder.as_markup()