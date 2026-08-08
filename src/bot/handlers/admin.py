import logging
import re
from math import ceil

from aiogram import Bot, F, Router, types
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.markdown import hbold
from aiogram_i18n import I18nContext
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.filters.admin import IsAdminFilter
from src.bot.keyboards import (
    get_cancel_admin_action_kb,
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
    get_users_filtered,
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
ADMIN_USER_FILTERS = {"all", "active", "inactive"}

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


class AdminUserListStates(StatesGroup):
    """Состояния FSM списка пользователей."""
    viewing_list = State()
    waiting_for_search = State()
    waiting_for_personal_message = State()


# --- MAIN NAVIGATION ---

@router.message(Command("admin"))
async def cmd_admin(message: types.Message):
    """Вход в админ-панель"""
    try:
        await message.delete()
    except Exception:
        pass
    text = (
        "👑 <b>Панель администратора</b>\n\n"
        "Добро пожаловать! Здесь вы можете управлять пользователями, "
        "выдавать блокировки и проверять статусы подписок."
    )
    await message.answer(text, reply_markup=get_admin_main_kb(), parse_mode="HTML")


@router.message(Command("access"), F.reply_to_message)
async def cmd_access(message: types.Message):
    """Копирует replied-сообщение в текущий чат без защиты контента."""
    try:
        await message.reply_to_message.copy_to(
            chat_id=message.chat.id,
            protect_content=False,
        )
        try:
            await message.delete()
        except Exception:
            pass
    except TelegramBadRequest as exc:
        logger.warning(
            "Не удалось снять protect_content через /access для chat_id=%s: %s",
            message.chat.id,
            exc,
        )
        await message.answer(
            "❌ Не удалось скопировать сообщение. Возможно, оно недоступно или его тип не поддерживается."
        )
    except Exception as exc:
        logger.error(
            "Ошибка при выполнении /access для chat_id=%s: %s",
            message.chat.id,
            exc,
            exc_info=True,
        )
        await message.answer("❌ Произошла ошибка при копировании сообщения.")


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
async def process_admin_page(
    callback: types.CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
):
    """Отображение списка пользователей с пагинацией"""
    page = int(callback.data.split("_")[2])

    await render_user_list(callback, session, state, page=page)
    await callback.answer()


@router.callback_query(F.data == "admin_filter_toggle")
async def process_admin_filter_toggle(
    callback: types.CallbackQuery, state: FSMContext, session: AsyncSession
):
    """Циклическое переключение фильтров: All -> VIP -> Free -> All"""
    data = await state.get_data()
    current_filter = data.get("filter_status", "all")

    order = ["all", "active", "inactive"]
    next_filter = order[(order.index(current_filter) + 1) % len(order)]

    await state.update_data(filter_status=next_filter, current_page=1)
    await render_user_list(callback, session, state)
    await callback.answer()


@router.callback_query(F.data == "admin_user_search")
async def process_admin_user_search_start(
    callback: types.CallbackQuery, state: FSMContext
):
    """Начало поиска пользователя"""
    await state.set_state(AdminUserListStates.waiting_for_search)
    await callback.message.answer(
        "🔍 <b>Поиск пользователя</b>\n\n"
        "Введите <b>username</b> (без @) или <b>Telegram ID</b>:",
        parse_mode="HTML",
        reply_markup=get_cancel_fsm_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_search_reset")
async def process_admin_search_reset(
    callback: types.CallbackQuery, state: FSMContext, session: AsyncSession
):
    """Сброс всех фильтров и поиска"""
    await state.update_data(filter_status="all", search_query=None, current_page=1)
    await render_user_list(callback, session, state)
    await callback.answer("Фильтры сброшены")


@router.callback_query(F.data.startswith("admin_send_msg:"))
async def process_admin_send_message_start(
    callback: types.CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    i18n: I18nContext,
):
    """Переводит админа в режим отправки личного сообщения пользователю."""
    user_id = int(callback.data.split(":", maxsplit=1)[1])
    user = await get_user_by_id(session, user_id)
    if not user:
        return await callback.answer(i18n.get("admin-personal-message-user-not-found"), show_alert=True)

    prompt_message = await callback.message.answer(
        i18n.get("admin-personal-message-prompt"),
        parse_mode="HTML",
        reply_markup=get_cancel_admin_action_kb(),
    )
    await state.set_state(AdminUserListStates.waiting_for_personal_message)
    await state.update_data(target_user_id=user_id, admin_action_msg_id=prompt_message.message_id)
    await callback.answer()


@router.callback_query(F.data == "cancel_admin_action")
async def process_cancel_admin_action(
    callback: types.CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    i18n: I18nContext,
):
    """Отменяет текущее персональное действие админа и возвращает к карточке пользователя."""
    data = await state.get_data()
    user_id = data.get("target_user_id")
    await state.clear()

    try:
        await callback.message.delete()
    except Exception:
        pass

    await callback.answer(i18n.get("admin-personal-message-cancelled"))

    if user_id:
        await show_user_card(callback.message, session, user_id)


@router.message(AdminUserListStates.waiting_for_search)
async def process_admin_user_search_input(
    message: types.Message, state: FSMContext, session: AsyncSession
):
    """Обработка ввода поискового запроса"""
    search_query = message.text.strip() if message.text else None

    if not search_query:
        return await message.answer("❌ Введите текст для поиска.")

    await state.update_data(search_query=search_query, current_page=1)
    # Удаляем сообщение админа для чистоты
    try:
        await message.delete()
    except Exception:
        pass

    await render_user_list(message, session, state)


@router.message(AdminUserListStates.waiting_for_personal_message)
async def process_admin_personal_message(
    message: types.Message,
    state: FSMContext,
    session: AsyncSession,
    i18n: I18nContext,
):
    """Копирует любое сообщение админа целевому пользователю через copy_to."""
    data = await state.get_data()
    user_id = data.get("target_user_id")
    admin_action_msg_id = data.get("admin_action_msg_id")

    if not user_id:
        await state.clear()
        return await message.answer(i18n.get("admin-personal-message-user-not-found"))

    try:
        await message.copy_to(chat_id=user_id)
        await message.answer(i18n.get("admin-personal-message-success", user_id=user_id))
    except TelegramForbiddenError:
        await message.answer(i18n.get("admin-personal-message-user-blocked"))
    except TelegramBadRequest as exc:
        logger.warning("Не удалось скопировать сообщение пользователю %s: %s", user_id, exc)
        await message.answer(i18n.get("admin-personal-message-copy-failed"))
    except Exception as exc:
        logger.error(
            "Ошибка при отправке персонального сообщения пользователю %s: %s",
            user_id,
            exc,
            exc_info=True,
        )
        await message.answer(i18n.get("admin-personal-message-copy-failed"))
    finally:
        await state.clear()
        if admin_action_msg_id:
            try:
                await message.bot.delete_message(chat_id=message.chat.id, message_id=admin_action_msg_id)
            except Exception:
                pass


@router.callback_query(F.data.startswith("admin_user_"))
async def process_admin_user_card(callback: types.CallbackQuery, session: AsyncSession):
    """Карточка конкретного пользователя"""
    user_id = int(callback.data.split("_")[2])

    if not await show_user_card(callback.message, session, user_id):
        return await callback.answer("Пользователь не найден в БД!", show_alert=True)

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


async def show_user_card(
    target_message: types.Message,
    session: AsyncSession,
    user_id: int,
) -> bool:
    """Отправляет карточку пользователя и клавиатуру управления."""
    user = await get_user_by_id(session, user_id)
    if not user:
        return False

    await target_message.answer(
        _format_user_card_text(user),
        reply_markup=get_user_manage_kb(user_id, user.is_blocked),
        parse_mode="HTML",
    )
    return True


def _normalize_admin_user_list_data(data: dict) -> dict[str, int | str | None]:
    """Нормализует FSM-данные списка пользователей."""
    current_page = data.get("current_page", 1)
    filter_status = data.get("filter_status", "all")
    search_query = data.get("search_query")

    try:
        current_page = max(int(current_page), 1)
    except (TypeError, ValueError):
        current_page = 1

    if filter_status not in ADMIN_USER_FILTERS:
        filter_status = "all"

    if isinstance(search_query, str):
        search_query = search_query.strip() or None
    else:
        search_query = None

    return {
        "current_page": current_page,
        "filter_status": filter_status,
        "search_query": search_query,
    }


def _format_user_list_text(total_users: int, filter_status: str, search_query: str | None) -> str:
    """Формирует текст списка пользователей с учетом активных критериев."""
    text_lines = [
        f"👥 <b>Список пользователей</b> (Всего: {total_users})",
    ]

    if filter_status != "all":
        filter_label = "Только с активной подпиской" if filter_status == "active" else "Только без активной подписки"
        text_lines.append(f"🎭 Фильтр: <b>{filter_label}</b>")

    if search_query:
        text_lines.append(f"🔍 Поиск: <b>{search_query}</b>")

    text_lines.append("")
    text_lines.append("Нажмите на пользователя для просмотра детальной информации и управления доступом.")
    return "\n".join(text_lines)


async def render_user_list(
    message_or_call: types.Message | types.CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    page: int | None = None,
):
    """Отрисовывает список пользователей на основе данных из FSM."""
    user_list_data = _normalize_admin_user_list_data(await state.get_data())
    if page is not None:
        user_list_data["current_page"] = max(page, 1)

    users, total_users = await get_users_filtered(
        session=session,
        page=user_list_data["current_page"],
        limit=USERS_PER_PAGE,
        status_filter=user_list_data["filter_status"],
        search_query=user_list_data["search_query"],
    )
    total_pages = ceil(total_users / USERS_PER_PAGE) if total_users > 0 else 1

    if user_list_data["current_page"] > total_pages:
        user_list_data["current_page"] = total_pages
        users, total_users = await get_users_filtered(
            session=session,
            page=user_list_data["current_page"],
            limit=USERS_PER_PAGE,
            status_filter=user_list_data["filter_status"],
            search_query=user_list_data["search_query"],
        )

    await state.set_state(AdminUserListStates.viewing_list)
    await state.update_data(**user_list_data)

    text = _format_user_list_text(
        total_users=total_users,
        filter_status=user_list_data["filter_status"],
        search_query=user_list_data["search_query"],
    )
    reply_markup = get_users_list_kb(
        users=users,
        page=user_list_data["current_page"],
        total_pages=total_pages,
        filter_status=user_list_data["filter_status"],
        search_query=user_list_data["search_query"],
    )

    if isinstance(message_or_call, types.Message):
        await message_or_call.answer(text, reply_markup=reply_markup, parse_mode="HTML")
        return

    await message_or_call.message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")
