import logging
from math import ceil
import re
from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from aiogram.exceptions import TelegramForbiddenError

from src.database.session import async_session
from src.database.crud.user_service import get_users_count, get_users_page, get_user_by_id, toggle_user_block
from src.core.security import SecurityManager
from src.bot.filters.admin import IsAdminFilter
from src.bot.keyboards import get_admin_main_kb, get_users_list_kb, get_user_manage_kb

logger = logging.getLogger(__name__)

router = Router()
router.message.filter(IsAdminFilter())
router.callback_query.filter(IsAdminFilter())

USERS_PER_PAGE = 10

@router.message(Command("admin"))
async def cmd_admin(message: types.Message):
    """Вход в админ-панель"""
    await message.delete()
    text = (
        "👑 <b>Панель администратора</b>\n\n"
        "Добро пожаловать! Здесь вы можете управлять пользователями, "
        "выдавать блокировки и проверять статусы подписок."
    )
    await message.answer(text, reply_markup=get_admin_main_kb(), parse_mode="HTML")

@router.callback_query(F.data == "admin_main")
async def process_admin_main(callback: types.CallbackQuery):
    """Возврат в главное меню админки"""
    text = (
        "👑 <b>Панель администратора</b>\n\n"
        "Добро пожаловать! Здесь вы можете управлять пользователями, "
        "выдавать блокировки и проверять статусы подписок."
    )
    await callback.message.edit_text(text, reply_markup=get_admin_main_kb(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("admin_page_"))
async def process_admin_page(callback: types.CallbackQuery):
    """Отображение списка пользователей (страницы)"""
    page = int(callback.data.split("_")[2])
    
    async with async_session() as session:
        total_users = await get_users_count(session)
        total_pages = ceil(total_users / USERS_PER_PAGE) if total_users > 0 else 1
        
        # Корректировка, если страница вышла за пределы
        if page > total_pages: page = total_pages
        if page < 1: page = 1
            
        offset = (page - 1) * USERS_PER_PAGE
        users = await get_users_page(session, limit=USERS_PER_PAGE, offset=offset)
        
    text = (
        f"👥 <b>Список пользователей (Всего: {total_users})</b>\n\n"
        f"Нажмите на пользователя для просмотра детальной информации и управления доступом."
    )
    
    await callback.message.edit_text(
        text, 
        reply_markup=get_users_list_kb(users, page, total_pages),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("admin_user_"))
async def process_admin_user_card(callback: types.CallbackQuery):
    """Отправляет НОВОЕ сообщение с карточкой пользователя"""
    user_id = int(callback.data.split("_")[2])
    
    async with async_session() as session:
        user = await get_user_by_id(session, user_id)
        
    if not user:
        return await callback.answer("Пользователь не найден в БД!", show_alert=True)
        
    name = f"@{user.username}" if user.username else "Нет юзернейма"
    reg_date = f"{user.created_at.strftime('%d.%m.%Y %H:%M')} UTC"
    
    sub_status = "❌ Нет"
    if user.subscription_end:
        sub_status = f"✅ До {user.subscription_end.strftime('%d.%m.%Y %H:%M')} UTC"
        
    trial_status = "✅ Использован" if user.is_trial_used else "❌ Не использован"
    block_status = "🚫 ЗАБЛОКИРОВАН" if user.is_blocked else "🟢 Активен"
    
    text = (
        f"👤 <b>Карточка пользователя</b>\n\n"
        f"<b>ID:</b> <code>{user.id}</code>\n"
        f"<b>Username:</b> {name}\n"
        f"<b>Дата регистрации:</b> {reg_date}\n\n"
        f"<b>Подписка:</b> {sub_status}\n"
        f"<b>Триал 24ч:</b> {trial_status}\n\n"
        f"<b>Статус:</b> {block_status}"
    )
    
    await callback.message.answer(
        text, 
        reply_markup=get_user_manage_kb(user.id, user.is_blocked),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("admin_toggle_"))
async def process_admin_toggle_block(callback: types.CallbackQuery, bot: Bot):
    """Блокировка / Разблокировка пользователя"""
    user_id = int(callback.data.split("_")[2])
    
    async with async_session() as session:
        new_status = await toggle_user_block(session, user_id)
        
    if new_status is None:
        return await callback.answer("Ошибка изменения статуса", show_alert=True)
        
    # Синхронизация с SecurityManager (мгновенная инвалидация кеша)
    if new_status:
        SecurityManager.block(user_id)
    else:
        SecurityManager.unblock(user_id)
        
    # Если заблокировали - шлем прощальное сообщение
    if new_status is True:
        try:
            await bot.send_message(
                user_id, 
                "❌ <b>Ваш аккаунт был заблокирован администрацией.</b>\nДоступ к функциям бота ограничен.",
                parse_mode="HTML"
            )
        except TelegramForbiddenError:
            pass # Юзер уже сам заблочил бота
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление о бане {user_id}: {e}")
            
    # Обновляем текст сообщения и клавиатуру у сообщения админа
    block_status = "🚫 ЗАБЛОКИРОВАН" if new_status else "🟢 Активен"
    
    # Пытаемся заменить статус в текущем тексте сообщения
    current_text = callback.message.html_text
    new_text = current_text
    
    if "Статус:" in current_text:
        # Ищем строку со статусом и заменяем её
        new_text = re.sub(r"<b>Статус:</b>.*", f"<b>Статус:</b> {block_status}", current_text)
    
    await callback.message.edit_text(
        text=new_text,
        reply_markup=get_user_manage_kb(user_id, new_status),
        parse_mode="HTML"
    )
    
    action = "заблокирован" if new_status else "разблокирован"
    await callback.answer(f"Пользователь {action}!", show_alert=True)
