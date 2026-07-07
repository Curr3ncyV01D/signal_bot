import logging
import re
from math import ceil

from aiogram import Bot, F, Router, types
from aiogram.exceptions import TelegramForbiddenError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.markdown import hbold
from aiogram_i18n import I18nContext
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.filters.admin import IsAdminFilter
from src.bot.keyboards import (
    get_admin_channel_kb,
    get_admin_main_kb,
    get_cancel_fsm_kb,
    get_close_button_kb,
    get_user_manage_kb,
    get_users_list_kb,
)
from src.core.config import config
from src.core.localization import normalize_locale_code
from src.core.security import SecurityManager
from src.database.crud.channel_service import ChannelService
from src.database.crud.user_service import (
    get_user_by_id,
    get_users_count,
    get_users_page,
    toggle_user_block,
    update_user_subscription,
)
from src.database.models import User
from src.services import analyzer
from src.services.dashboard import recreate_dashboard_logic
from src.utils import format_datetime, format_smart_num, parse_numeric_input

logger = logging.getLogger(__name__)

router = Router()
router.message.filter(IsAdminFilter())
router.callback_query.filter(IsAdminFilter())

# --- CONSTANTS & STATES ---

USERS_PER_PAGE = 10

class AdminChannelStates(StatesGroup):
    """Состояния FSM для админ-панели"""
    waiting_for_volume = State()
    waiting_for_cascade = State()
    waiting_for_oi = State()
    waiting_for_sub_days = State()
    waiting_for_symbol_search = State()
    waiting_for_channel_mcap_pct = State()
    waiting_for_channel_mcap_min_usd = State()
    waiting_for_channel_mcap_cas_pct = State()
    waiting_for_channel_mcap_cas_min_usd = State()


# --- MAIN NAVIGATION ---

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


# --- USER MANAGEMENT ---

@router.callback_query(F.data.startswith("admin_page_"))
async def process_admin_page(callback: types.CallbackQuery, session: AsyncSession):
    """Отображение списка пользователей с пагинацией"""
    page = int(callback.data.split("_")[2])
    
    total_users = await get_users_count(session)
    total_pages = ceil(total_users / USERS_PER_PAGE) if total_users > 0 else 1
    
    # Корректировка границ страниц
    page = max(1, min(page, total_pages))
            
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
async def process_admin_user_card(callback: types.CallbackQuery, session: AsyncSession):
    """Карточка конкретного пользователя"""
    user_id = int(callback.data.split("_")[2])
    
    user = await get_user_by_id(session, user_id)
    if not user:
        return await callback.answer("Пользователь не найден в БД!", show_alert=True)
            
    text = _format_user_card_text(user)
    
    await callback.message.answer(
        text, 
        reply_markup=get_user_manage_kb(user_id, user.is_blocked),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_toggle_"))
async def process_admin_toggle_block(
    callback: types.CallbackQuery,
    bot: Bot,
    session: AsyncSession,
    i18n: I18nContext,
):
    """Блокировка / Разблокировка пользователя"""
    user_id = int(callback.data.split("_")[2])
    user = await get_user_by_id(session, user_id)
    
    new_status = await toggle_user_block(session, user_id)
    if new_status is None:
        return await callback.answer("Ошибка изменения статуса", show_alert=True)
        
    # Синхронизация с SecurityManager
    if new_status:
        SecurityManager.block(user_id)
    else:
        SecurityManager.unblock(user_id)
        
    # Уведомление пользователя о блокировке
    if new_status is True:
        try:
            user_locale = normalize_locale_code(user.language_code if user else None)
            with i18n.use_locale(user_locale):
                await bot.send_message(
                    user_id,
                    i18n.get("admin-user-blocked-notification"),
                    parse_mode="HTML",
                    reply_markup=get_close_button_kb(),
                )
        except (TelegramForbiddenError, Exception):
            pass
            
    # Обновление UI
    block_status = "🚫 ЗАБЛОКИРОВАН" if new_status else "🟢 Активен"
    current_text = callback.message.html_text
    new_text = re.sub(r"<b>Статус:</b>.*", f"<b>Статус:</b> {block_status}", current_text)
    
    await callback.message.edit_text(
        text=new_text,
        reply_markup=get_user_manage_kb(user_id, new_status),
        parse_mode="HTML"
    )
    
    action = "заблокирован" if new_status else "разблокирован"
    await callback.answer(f"Пользователь {action}!", show_alert=True)


@router.callback_query(F.data.startswith("admin_subs_"))
async def process_admin_subs_start(callback: types.CallbackQuery, state: FSMContext):
    """Начало изменения срока подписки"""
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
async def process_admin_subs_days(
    message: types.Message,
    state: FSMContext,
    bot: Bot,
    session: AsyncSession,
    i18n: I18nContext,
):
    """Обработка ввода дней подписки"""
    data = await state.get_data()
    user_id = data.get("target_user_id")
    fsm_msg_id = data.get("fsm_msg_id")
    
    if not message.text or not message.text.isdigit():
        return await message.answer("❌ Введите целое число дней.", reply_markup=get_cancel_fsm_kb())
        
    days = int(message.text)
    if not (0 <= days <= config.MAX_SUB_DAYS):
        return await message.answer(f"❌ Число от 0 до {config.MAX_SUB_DAYS}.", reply_markup=get_cancel_fsm_kb())
        
    user = await update_user_subscription(session, user_id, days)
    if not user:
        await state.clear()
        return await message.answer("❌ Ошибка: пользователь не найден.")
            
    # Cleanup & Notify
    if fsm_msg_id:
        try: await bot.delete_message(chat_id=message.chat.id, message_id=fsm_msg_id)
        except Exception: pass

    try:
        user_locale = normalize_locale_code(user.language_code)
        with i18n.use_locale(user_locale):
            notify_text = (
                i18n.get(
                    "admin-user-subscription-updated-notification",
                    subscription_end=hbold(format_datetime(user.subscription_end)),
                )
                if days > 0
                else i18n.get("admin-user-subscription-cancelled-notification")
            )
            await bot.send_message(
                user_id,
                notify_text,
                parse_mode="HTML",
                reply_markup=get_close_button_kb(),
            )
    except Exception: pass
        
    status = f"установлена на {days} дн." if days > 0 else "аннулирована"
    await message.answer(f"✅ Подписка пользователя {user_id} {status}!")
    await state.clear()


# --- CHANNEL SETTINGS ---

@router.callback_query(F.data == "admin_channel_settings")
async def process_admin_channel_settings(callback: types.CallbackQuery, session: AsyncSession):
    """Главное меню настроек канала"""
    await render_channel_settings(callback, session)
    await callback.answer()


@router.callback_query(F.data.startswith("admin_chan_toggle_"))
async def process_admin_chan_toggle(callback: types.CallbackQuery, session: AsyncSession):
    """Переключение тумблеров алертов канала"""
    action = callback.data.replace("admin_chan_toggle_", "")
    
    # Обработка смены режима (USD/PERCENT) отдельно
    if action == "threshold_mode":
        settings = await ChannelService.get_settings(session)
        new_mode = "PERCENT" if settings.threshold_mode == "USD" else "USD"
        await ChannelService.update_settings(session, threshold_mode=new_mode)
        await callback.answer(f"Режим канала изменен на {new_mode}")
    else:
        settings = await ChannelService.get_settings(session)
        update_map = {
            "active": "is_active", "cascade": "alert_cascade", "volume": "alert_volume",
            "squeeze": "alert_squeeze", "oi": "alert_oi", "rsi": "alert_rsi",
            "cvd": "alert_cvd", "longs": "alert_longs", "shorts": "alert_shorts"
        }
        if action in update_map:
            field = update_map[action]
            await ChannelService.update_settings(session, **{field: not getattr(settings, field)})
            await callback.answer("Настройка обновлена!")

    await analyzer.invalidate_user_cache()
    await render_channel_settings(callback, session)


@router.callback_query(F.data.in_(["admin_chan_set_vol", "admin_chan_set_cas", "admin_chan_set_oi"]))
async def process_chan_threshold_start(callback: types.CallbackQuery, state: FSMContext):
    """Начало ввода числовых порогов"""
    if callback.data == "admin_chan_set_vol":
        await state.set_state(AdminChannelStates.waiting_for_volume)
        await callback.message.answer("Введите глобальный порог объема для канала (в $):")
    elif callback.data == "admin_chan_set_cas":
        await state.set_state(AdminChannelStates.waiting_for_cascade)
        await callback.message.answer("Введите глобальный порог каскада для канала (в $):")
    elif callback.data == "admin_chan_set_oi":
        await state.set_state(AdminChannelStates.waiting_for_oi)
        await callback.message.answer("Введите пороги ОИ (Процент и Сумма через пробел, например: 10 1000000):")
    await callback.answer()


@router.message(AdminChannelStates.waiting_for_volume)
@router.message(AdminChannelStates.waiting_for_cascade)
@router.message(AdminChannelStates.waiting_for_oi)
async def process_admin_channel_thresholds(message: types.Message, state: FSMContext, session: AsyncSession):
    """Обработка ввода числовых порогов"""
    current_state = await state.get_state()
    update_data = {}

    if current_state == AdminChannelStates.waiting_for_oi:
        parts = message.text.replace("%", "").replace("$", "").split()
        try:
            if len(parts) != 2: raise ValueError
            pct, val = parse_numeric_input(parts[0]), parse_numeric_input(parts[1])
            if pct <= 0 or val <= 0: raise ValueError
            update_data = {"threshold_oi_percent": pct, "threshold_oi_value": val}
        except ValueError:
            return await message.answer("❌ Введите 2 положительных числа через пробел.")
    else:
        val = parse_numeric_input(message.text.replace("$", ""))
        if val is None or val <= 0:
            return await message.answer("❌ Введите корректное число.")
        field = "threshold" if current_state == AdminChannelStates.waiting_for_volume else "threshold_cascade"
        update_data[field] = val
            
    await ChannelService.update_settings(session, **update_data)
    await analyzer.invalidate_user_cache()
    await state.clear()
    await render_channel_settings(message, session)
    await message.answer("✅ Настройки канала обновлены.")


# --- CHANNEL MCAP SETTINGS ---

@router.callback_query(F.data.startswith("admin_chan_set_mcap_"))
async def admin_chan_set_mcap_start(callback: types.CallbackQuery, state: FSMContext):
    """Начало настройки параметров режима PERCENT"""
    data = callback.data
    states_map = {
        "admin_chan_set_mcap_pct": (AdminChannelStates.waiting_for_channel_mcap_pct, "Введите порог объема в % (напр. 0.005)"),
        "admin_chan_set_mcap_min_usd": (AdminChannelStates.waiting_for_channel_mcap_min_usd, "Введите мин. пол объема в $ (напр. 50000)"),
        "admin_chan_set_mcap_cas_pct": (AdminChannelStates.waiting_for_channel_mcap_cas_pct, "Введите порог каскада в % (напр. 0.01)"),
        "admin_chan_set_mcap_cas_min_usd": (AdminChannelStates.waiting_for_channel_mcap_cas_min_usd, "Введите мин. пол каскада в $ (напр. 100000)")
    }
    
    if data in states_map:
        target_state, text = states_map[data]
        await state.set_state(target_state)
        await callback.message.answer(f"КАНАЛ: {text}")
    
    await callback.answer()


@router.message(AdminChannelStates.waiting_for_channel_mcap_pct)
@router.message(AdminChannelStates.waiting_for_channel_mcap_min_usd)
@router.message(AdminChannelStates.waiting_for_channel_mcap_cas_pct)
@router.message(AdminChannelStates.waiting_for_channel_mcap_cas_min_usd)
async def process_admin_mcap_parameter(message: types.Message, state: FSMContext, session: AsyncSession):
    """Обработка ввода параметров MCAP"""
    val = parse_numeric_input(message.text)
    if val is None or val < 0:
        return await message.answer("❌ Введите положительное число.")

    current_state = await state.get_state()
    field_map = {
        AdminChannelStates.waiting_for_channel_mcap_pct: "threshold_mcap_pct",
        AdminChannelStates.waiting_for_channel_mcap_min_usd: "threshold_mcap_usd_min",
        AdminChannelStates.waiting_for_channel_mcap_cas_pct: "threshold_cascade_mcap_pct",
        AdminChannelStates.waiting_for_channel_mcap_cas_min_usd: "threshold_cascade_mcap_usd_min"
    }
    
    if current_state in field_map:
        await ChannelService.update_settings(session, **{field_map[current_state]: val})
        await analyzer.invalidate_user_cache()
        await state.clear()
        await render_channel_settings(message, session)
        await message.answer("✅ Настройки канала обновлены.")


# --- SYSTEM ACTIONS ---

@router.callback_query(F.data == "admin_chan_restart_dash")
async def process_restart_dash(callback: types.CallbackQuery, bot: Bot, liq_aggregator, market_aggregator, session: AsyncSession):
    """Пересоздание дэшборда в канале"""
    try:
        message_id = await recreate_dashboard_logic(bot, liq_aggregator, market_aggregator)
        if message_id is None:
            await callback.answer("⏳ Пересоздание уже выполняется.", show_alert=True)
        else:
            await callback.answer("✅ Дэшборд пересоздан!", show_alert=True)
        await render_channel_settings(callback, session)
    except Exception as e:
        logger.error(f"Ошибка дэшборда: {e}", exc_info=True)
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


# --- COMMON / FSM ---

@router.callback_query(F.data == "admin_fsm_stop")
async def process_admin_fsm_stop(callback: types.CallbackQuery, state: FSMContext):
    """Сброс FSM и очистка интерфейса"""
    await state.clear()
    try: await callback.message.delete()
    except Exception: pass
    await callback.answer("Ввод отменен")


# --- HELPERS ---

def _format_user_card_text(user: User) -> str:
    """Форматирование карточки пользователя"""
    return (
        f"👤 <b>Карточка пользователя</b>\n\n"
        f"<b>ID:</b> <code>{user.id}</code>\n"
        f"<b>Username:</b> @{user.username if user.username else 'N/A'}\n"
        f"<b>Регистрация:</b> {format_datetime(user.created_at)}\n\n"
        f"<b>Подписка:</b> {'✅ До ' + format_datetime(user.subscription_end) if user.subscription_end else '❌ Нет'}\n"
        f"<b>Триал 24ч:</b> {'✅ Да' if user.is_trial_used else '❌ Нет'}\n\n"
        f"<b>Статус:</b> {'🚫 ЗАБЛОКИРОВАН' if user.is_blocked else '🟢 Активен'}"
    )


async def render_channel_settings(message_or_call, session: AsyncSession):
    """Отрисовка меню настроек канала"""
    settings = await ChannelService.get_settings(session)
    text = (
        f"📢 <b>Настройки VIP-Канала (Режим: {settings.threshold_mode})</b>\n\n"
        f"<b>Статус постинга:</b> {'🟢 АКТИВЕН' if settings.is_active else '🔴 ОТКЛЮЧЕН'}\n\n"
        f"<b>📊 Фильтры ликвидаций:</b>\n"
        f"🔶 Порог объема: <b>${format_smart_num(settings.threshold)}</b>\n"
        f"🔸 Порог каскада: <b>${format_smart_num(settings.threshold_cascade)}</b>\n"
        f"🔷 Порог объема MCAP: <b>{settings.threshold_mcap_pct}%</b> (мин. <b>${format_smart_num(settings.threshold_mcap_usd_min)}</b>)\n"
        f"🔹 Порог каскада MCAP: <b>{settings.threshold_cascade_mcap_pct}%</b> (мин. <b>${format_smart_num(settings.threshold_cascade_mcap_usd_min)}</b>)\n\n"
        f"<b>📊 Фильтры аналитики (OI):</b>\n"
        f"📈 Мин. рост OI: <b>{format_smart_num(settings.threshold_oi_percent, is_percent=True)}</b> и <b>${format_smart_num(settings.threshold_oi_value)}</b>\n\n"
        f"<i>Здесь вы настраиваете глобальные фильтры канала.</i>"
    )
    markup = get_admin_channel_kb(settings)
    
    if isinstance(message_or_call, types.Message):
        await message_or_call.answer(text, reply_markup=markup, parse_mode="HTML")
    else:
        try: await message_or_call.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
        except Exception: pass
