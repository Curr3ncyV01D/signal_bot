import asyncio
import logging
from datetime import datetime, timezone
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.utils.markdown import hbold
from aiogram.exceptions import TelegramBadRequest

from src.core.config import config
from src.database.session import async_session
from src.database.crud.user_service import get_or_create_user, activate_trial
from src.database.models import User
from src.bot.keyboards import get_start_kb, get_status_kb

logger = logging.getLogger(__name__)
router = Router()

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    async with async_session() as session:
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username)
    
    text = (
        f"👋 Добро пожаловать, {hbold(message.from_user.full_name)}!\n\n"
        f"Я профессиональный терминал для мониторинга ликвидаций на Bybit.\n"
        f"Вы будете получать уведомления, когда на рынке начнутся сильные движения.\n\n"
        f"👇 Выберите действие ниже:"
    )
    await message.answer(text, reply_markup=get_start_kb(user), parse_mode="HTML")

@router.callback_query(F.data == "activate_trial")
async def process_activate_trial(callback: types.CallbackQuery):
    """Обработка нажатия на кнопку получения триала"""
    async with async_session() as session:
        success, msg = await activate_trial(session, callback.from_user.id)
        user = await session.get(User, callback.from_user.id)
    
    if not success:
        return await callback.answer(msg, show_alert=True)
        
    await callback.answer("Успешно!", show_alert=False)
    
    # Обновляем клавиатуру (кнопка триала пропадет, появится "Зайти в канал")
    await callback.message.edit_reply_markup(reply_markup=get_start_kb(user))
    
    try:
        invite_link = await callback.bot.create_chat_invite_link(
            chat_id=config.PRIVATE_CHANNEL_ID,
            name=f"Trial_{callback.from_user.id}",
            creates_join_request=True
        )
        await callback.message.answer(
            f"🎉 <b>Триал активирован на 24 часа!</b>\n\n"
            f"Подайте заявку на вступление в закрытый канал по ссылке ниже. "
            f"Бот автоматически её одобрит.\n\n👉 {invite_link.invite_link}",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Ошибка создания ссылки в канал: {e}")
        await callback.message.answer(
            "✅ Триал активирован!\n\n"
            "<i>(Ошибка: Бот не имеет прав администратора в закрытом канале для создания ссылки. "
            "Пожалуйста, сообщите администратору.)</i>",
            parse_mode="HTML"
        )

@router.callback_query(F.data == "get_channel_link")
async def process_get_channel_link(callback: types.CallbackQuery):
    """Кнопка для получения ссылки, если подписка уже активна"""
    try:
        invite_link = await callback.bot.create_chat_invite_link(
            chat_id=config.PRIVATE_CHANNEL_ID,
            name=f"Sub_{callback.from_user.id}",
            creates_join_request=True
        )
        await callback.message.answer(f"👉 Ваша ссылка для входа в канал:\n{invite_link.invite_link}")
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка выдачи ссылки: {e}")
        await callback.answer("Ошибка получения ссылки. Бот не админ.", show_alert=True)

def generate_status_text(listener, liq_aggregator, data_queue: asyncio.Queue) -> str:
    """Хелпер для генерации текста статуса (используется в команде и кнопке Обновить)"""
    active_symbols = len(liq_aggregator.history)
    total_in_mem = sum(len(d) for d in liq_aggregator.history.values())

    total_pool = len(listener.ws_connections) if hasattr(listener, 'ws_connections') else 0
    active_pool = listener.get_active_connections_count() if hasattr(listener, 'get_active_connections_count') else 0

    status_emoji = "✅" if active_pool >= max(1, total_pool * 3 / 4) else "⚠️"
    if active_pool == 0: status_emoji = "❌"

    last_msg_str = "Никогда"
    if listener and hasattr(listener, 'last_message_time') and listener.last_message_time:
        diff = (datetime.now(timezone.utc).replace(tzinfo=None) - listener.last_message_time).total_seconds()
        if diff < 1:
            last_msg_str = f"{diff:.2f} сек. назад"
        else:
            last_msg_str = f"{int(diff)} сек. назад"
    
    queue_size = data_queue.qsize()
    queue_status = "🟢" if queue_size < 50 else "🟡" if queue_size < 200 else "🔴"

    return (
        f"{status_emoji} {hbold('Система активна')}\n\n"
        f"🌐 Соединения: {hbold(active_pool)} / {hbold(total_pool)}\n"
        f"💓 Последний сигнал API: {hbold(last_msg_str)}\n\n"
        f"📡 Мониторинг пар: {hbold(active_symbols)}\n"
        f"🧠 Событий в кэше: {hbold(total_in_mem)}\n"
        f"{queue_status} {hbold('Очередь обработки:')} {hbold(queue_size)}\n\n"
        f"🕒 Время сервера: {datetime.now(timezone.utc).replace(tzinfo=None).strftime('%H:%M:%S')} UTC"
    )

@router.message(Command("status"))
async def cmd_status(message: types.Message, listener, liq_aggregator, data_queue: asyncio.Queue):
    """Вызов статуса через команду"""
    await message.delete()
    text = generate_status_text(listener, liq_aggregator, data_queue)
    await message.answer(text, reply_markup=get_status_kb(), parse_mode="HTML")

@router.callback_query(F.data == "refresh_status")
async def process_refresh_status(callback: types.CallbackQuery, listener, liq_aggregator, data_queue: asyncio.Queue):
    """Обновление статуса по кнопке (меняет текст сообщения)"""
    text = generate_status_text(listener, liq_aggregator, data_queue)
    try:
        await callback.message.edit_text(text, reply_markup=get_status_kb(), parse_mode="HTML")
        await callback.answer("✅ Статус успешно обновлен!")
    except TelegramBadRequest as e:
        # Игнорируем ошибку "Message is not modified", если за секунду статус не поменялся
        if "message is not modified" in str(e).lower():
            await callback.answer("🔄 Данные не изменились", show_alert=False)
        else:
            logger.error(f"Ошибка при обновлении статуса: {e}")
            await callback.answer("Ошибка обновления", show_alert=True)