import logging
from math import ceil
import re
from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from aiogram.exceptions import TelegramForbiddenError
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.utils.markdown import hbold

from src.core.config import config
from src.database.models import User
from src.database.session import async_session
from src.database.crud.channel_service import ChannelService 
from src.database.crud.user_service import (
    get_users_count, get_users_page, get_user_by_id, 
    toggle_user_block, update_user_subscription
)
from src.core.security import SecurityManager
from src.bot.filters.admin import IsAdminFilter
from src.bot.keyboards import (
    get_admin_main_kb, get_users_list_kb, 
    get_user_manage_kb, get_admin_channel_kb,
    get_close_button_kb, get_cancel_fsm_kb
)
from src.services import analyzer
from src.services.dashboard import recreate_dashboard_logic
from src.utils import format_datetime, format_smart_num, parse_numeric_input

logger = logging.getLogger(__name__)

router = Router()
router.message.filter(IsAdminFilter())
router.callback_query.filter(IsAdminFilter())

class AdminChannelStates(StatesGroup):
    waiting_for_volume = State()
    waiting_for_cascade = State()
    waiting_for_oi = State()
    waiting_for_sub_days = State()
    waiting_for_symbol_search = State()

USERS_PER_PAGE = 10

def _format_user_card_text(user: User) -> str:
    """Форматирует текст карточки пользователя для админ-панели."""
    name = f"@{user.username}" if user.username else "Нет юзернейма"
    reg_date = format_datetime(user.created_at)
    
    sub_status = "❌ Нет"
    if user.subscription_end:
        sub_status = f"✅ До {format_datetime(user.subscription_end)}"
        
    trial_status = "✅ Использован" if user.is_trial_used else "❌ Не использован"
    block_status = "🚫 ЗАБЛОКИРОВАН" if user.is_blocked else "🟢 Активен"
    
    return (
        f"👤 <b>Карточка пользователя</b>\n\n"
        f"<b>ID:</b> <code>{user.id}</code>\n"
        f"<b>Username:</b> {name}\n"
        f"<b>Дата регистрации:</b> {reg_date}\n\n"
        f"<b>Подписка:</b> {sub_status}\n"
        f"<b>Триал 24ч:</b> {trial_status}\n\n"
        f"<b>Статус:</b> {block_status}"
    )

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
            
        text = _format_user_card_text(user)
        is_blocked = user.is_blocked
    
    await callback.message.answer(
        text, 
        reply_markup=get_user_manage_kb(user_id, is_blocked),
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


async def render_channel_settings(message_or_call, session):
    """Хелпер для отрисовки меню настроек канала"""
    settings = await ChannelService.get_settings(session)

    text = (
        f"📢 <b>Настройки VIP-Канала</b>\n\n"
        f"<b>Статус постинга:</b> {'🟢 АКТИВЕН' if settings.is_active else '🔴 ОТКЛЮЧЕН'}\n\n"
        f"<b>📊 Фильтры ликвидаций:</b>\n"
        f"🔸 Порог объема: <b>${format_smart_num(settings.threshold)}</b>\n"
        f"🔸 Порог каскада: <b>${format_smart_num(settings.threshold_cascade)}</b>\n\n"
        f"<b>📈 Фильтры аналитики (OI):</b>\n"
        f"🔸 Мин. рост OI: <b>{format_smart_num(settings.threshold_oi_percent, is_percent=True)}</b> и <b>${format_smart_num(settings.threshold_oi_value)}</b>\n\n"
        f"<i>Здесь вы настраиваете глобальные фильтры. Сигналы ниже этих значений в канал не попадут.</i>"
    )
    markup = get_admin_channel_kb(settings)
    
    if isinstance(message_or_call, types.Message):
        await message_or_call.answer(text, reply_markup=markup, parse_mode="HTML")
    else:
        try:
            await message_or_call.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
        except Exception as e:
            if "message is not modified" in str(e).lower():
                return
            logger.error(f"Ошибка при обновлении меню настроек: {e}")

@router.callback_query(F.data == "admin_channel_settings")
async def process_admin_channel_settings(callback: types.CallbackQuery):
    async with async_session() as session:
        await render_channel_settings(callback, session)
    await callback.answer()

@router.callback_query(F.data.startswith("admin_chan_toggle_"))
async def process_admin_chan_toggle(callback: types.CallbackQuery):
    """Универсальный обработчик всех тумблеров канала"""
    action = callback.data.replace("admin_chan_toggle_", "")
    
    async with async_session() as session:
        settings = await ChannelService.get_settings(session)
        
        # Меняем нужный флаг
        if action == "active": settings.is_active = not settings.is_active
        elif action == "cascade": settings.alert_cascade = not settings.alert_cascade
        elif action == "volume": settings.alert_volume = not settings.alert_volume
        elif action == "squeeze": settings.alert_squeeze = not settings.alert_squeeze
        elif action == "oi": settings.alert_oi = not settings.alert_oi
        elif action == "rsi": settings.alert_rsi = not settings.alert_rsi
        elif action == "cvd": settings.alert_cvd = not settings.alert_cvd
        elif action == "longs": settings.alert_longs = not settings.alert_longs
        elif action == "shorts": settings.alert_shorts = not settings.alert_shorts
        
        # Обновляем через сервис (он сам обновит кэш)
        await ChannelService.update_settings(session, **{
            "is_active": settings.is_active,
            "alert_cascade": settings.alert_cascade,
            "alert_volume": settings.alert_volume,
            "alert_squeeze": settings.alert_squeeze,
            "alert_oi": settings.alert_oi,
            "alert_rsi": settings.alert_rsi,
            "alert_cvd": settings.alert_cvd,
            "alert_longs": settings.alert_longs,
            "alert_shorts": settings.alert_shorts
        })
        # Сбрасываем кэш анализатора для мгновенного применения
        analyzer.invalidate_user_cache()
        
        await render_channel_settings(callback, session)
    await callback.answer("Настройка канала обновлена!")

# --- ВВОД ПОРОГОВ КАНАЛА ---

@router.callback_query(F.data == "admin_chan_set_vol")
async def set_chan_vol(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите глобальный порог объема для канала (в $):")
    await state.set_state(AdminChannelStates.waiting_for_volume)
    await callback.answer()

@router.message(AdminChannelStates.waiting_for_volume)
async def process_chan_vol(message: types.Message, state: FSMContext):
    try:
        val = parse_numeric_input(message.text.replace("$", ""))
        if val <= 0:
            raise ValueError
        async with async_session() as session:
            await ChannelService.update_settings(session, threshold=val)
            analyzer.invalidate_user_cache()
            await render_channel_settings(message, session)
        await state.clear()
    except ValueError:
        await message.answer("❌ Пожалуйста, введите корректную сумму цифрами")

@router.callback_query(F.data == "admin_chan_set_cas")
async def set_chan_cas(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите глобальный порог каскада для канала (в $):")
    await state.set_state(AdminChannelStates.waiting_for_cascade)
    await callback.answer()

@router.message(AdminChannelStates.waiting_for_cascade)
async def process_chan_cas(message: types.Message, state: FSMContext):
    try:
        val = parse_numeric_input(message.text.replace("$", ""))
        if val <= 0:
            raise ValueError
        async with async_session() as session:
            await ChannelService.update_settings(session, threshold_cascade=val)
            analyzer.invalidate_user_cache()
            await render_channel_settings(message, session)
        await state.clear()
    except ValueError:
        await message.answer("❌ Пожалуйста, введите корректную сумму цифрами")

@router.callback_query(F.data == "admin_chan_set_oi")
async def set_chan_oi(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите пороги ОИ для канала (Процент и Сумма через пробел, например: 10 1000000):")
    await state.set_state(AdminChannelStates.waiting_for_oi)
    await callback.answer()

@router.message(AdminChannelStates.waiting_for_oi)
async def process_chan_oi(message: types.Message, state: FSMContext):
    try:
        parts = message.text.replace("%", "").replace("$", "").split()
        if len(parts) != 2:
            raise ValueError
        pct = parse_numeric_input(parts[0])
        val = parse_numeric_input(parts[1])
        if pct <= 0 or val <= 0:
            raise ValueError
        
        async with async_session() as session:
            await ChannelService.update_settings(session, threshold_oi_percent=pct, threshold_oi_value=val)
            analyzer.invalidate_user_cache()
            await render_channel_settings(message, session)
        await state.clear()
    except ValueError:
        await message.answer("❌ Пожалуйста, введите корректную сумму цифрами")

@router.callback_query(F.data == "admin_chan_restart_dash")
async def process_restart_dash(
    callback: types.CallbackQuery, 
    bot: Bot, 
    liq_aggregator, 
    market_aggregator
):
    try:
        message_id = await recreate_dashboard_logic(bot, liq_aggregator, market_aggregator)
        if message_id is None:
            await callback.answer("⏳ Пересоздание дэшборда уже выполняется.", show_alert=True)
        else:
            await callback.answer("✅ Дэшборд успешно пересоздан и закреплен!", show_alert=True)

        async with async_session() as session:
            await render_channel_settings(callback, session)
            
    except Exception as e:
        logger.error(f"Ошибка при перезапуске дэшборда: {e}", exc_info=True)
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

# --- УПРАВЛЕНИЕ ПОДПИСКОЙ ---

@router.callback_query(F.data == "admin_fsm_stop")
async def process_admin_fsm_stop(callback: types.CallbackQuery, state: FSMContext):
    """Сброс FSM и удаление сообщения с вопросом"""
    await state.clear()
    try:
        await callback.message.delete()
    except Exception as e:
        logger.error(f"Ошибка при удалении сообщения FSM: {e}")
    await callback.answer("Ввод отменен")

@router.callback_query(F.data.startswith("admin_subs_"))
async def process_admin_subs_start(callback: types.CallbackQuery, state: FSMContext):
    """Начало процесса изменения подписки"""
    user_id = int(callback.data.split("_")[2])
    await state.update_data(target_user_id=user_id)
    await state.set_state(AdminChannelStates.waiting_for_sub_days)
    
    msg = await callback.message.answer(
        f"📅 <b>Изменение срока подписки</b>\n\n"
        f"Введите количество дней (от 0 до {config.MAX_SUB_DAYS}):\n"
        "• <b>0</b> — аннулировать подписку\n"
        f"• <b>1-{config.MAX_SUB_DAYS}</b> — установить новый срок от текущего момента",
        parse_mode="HTML",
        reply_markup=get_cancel_fsm_kb()
    )
    await state.update_data(fsm_msg_id=msg.message_id)
    await callback.answer()

@router.message(AdminChannelStates.waiting_for_sub_days)
async def process_admin_subs_days(message: types.Message, state: FSMContext, bot: Bot):
    """Обработка ввода количества дней"""
    data = await state.get_data()
    user_id = data.get("target_user_id")
    fsm_msg_id = data.get("fsm_msg_id")
    
    if not message.text or not message.text.isdigit():
        return await message.answer("❌ Введите целое число дней (например: 30).", reply_markup=get_cancel_fsm_kb())
        
    days = int(message.text)
    if days < 0 or days > config.MAX_SUB_DAYS:
        return await message.answer(f"❌ Введите число от 0 до {config.MAX_SUB_DAYS}.", reply_markup=get_cancel_fsm_kb())
        
    async with async_session() as session:
        user = await update_user_subscription(session, user_id, days)
        
        if not user:
            await state.clear()
            return await message.answer("❌ Ошибка: пользователь не найден в базе данных.")
            
        sub_end = user.subscription_end

    # Удаляем сообщение с вопросом
    if fsm_msg_id:
        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=fsm_msg_id)
        except Exception:
            pass

    # Уведомление пользователя
    try:
        if days > 0:
            notify_text = (
                f"📅 <b>Ваша подписка обновлена администратором!</b>\n\n"
                f"Новый срок действия: {hbold(format_datetime(sub_end))}"
            )
        else:
            notify_text = "❌ <b>Ваша подписка была аннулирована администратором.</b>"
            
        await bot.send_message(user_id, notify_text, parse_mode="HTML", reply_markup=get_close_button_kb())
    except TelegramForbiddenError:
        logger.warning(f"Не удалось уведомить {user_id}: бот заблокирован")
    except Exception as e:
        logger.error(f"Ошибка уведомления {user_id}: {e}")
        
    # Подтверждение админу
    status = f"установлена на {days} дн." if days > 0 else "аннулирована"
    await message.answer(f"✅ Подписка пользователя {user_id} {status}!")
    
    await state.clear()
