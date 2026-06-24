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
from src.bot.keyboards import get_start_kb, get_status_kb, get_close_button_kb
from src.services.metrics_service import MetricsService

logger = logging.getLogger(__name__)
router = Router()

def get_main_menu_text(full_name: str) -> str:
    """Текст главного меню."""
    return (
        f"👋 Добро пожаловать, {hbold(full_name)}!\n\n"
        f"Я профессиональный терминал для мониторинга ликвидаций на Bybit.\n"
        f"Вы будете получать уведомления, когда на рынке начнутся сильные движения.\n\n"
        f"👇 Выберите действие ниже:"
    )

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    # Парсинг реферального кода из команды (например: /start ref_12345 или /start 12345)
    referrer_id = None
    if message.text and len(message.text.split()) > 1:
        ref_arg = message.text.split()[1]
        ref_arg = ref_arg.replace("ref_", "")
        if ref_arg.isdigit():
            parsed_ref = int(ref_arg)
            # Запрещаем указывать самого себя как реферера
            if parsed_ref != message.from_user.id:
                referrer_id = parsed_ref

    async with async_session() as session:
        user = await get_or_create_user(
            session, 
            message.from_user.id, 
            message.from_user.username,
            referrer_id=referrer_id
        )
    
    text = get_main_menu_text(message.from_user.full_name)
    await message.answer(text, reply_markup=get_start_kb(user), parse_mode="HTML")

@router.callback_query(F.data == "back_to_main")
async def process_back_to_main(callback: types.CallbackQuery):
    """Возврат в главное меню из настроек"""
    async with async_session() as session:
        user = await session.get(User, callback.from_user.id)
        if not user:
            return await callback.answer("Ошибка профиля", show_alert=True)
    
    text = get_main_menu_text(callback.from_user.full_name)
    await callback.message.edit_text(text, reply_markup=get_start_kb(user), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "activate_trial")
async def process_activate_trial(callback: types.CallbackQuery):
    """Обработка нажатия на кнопку получения пробного периода"""
    async with async_session() as session:
        success, msg = await activate_trial(session, callback.from_user.id)
        user = await session.get(User, callback.from_user.id)
    
    if not success:
        return await callback.answer(msg, show_alert=True)
        
    await callback.answer("Успешно!", show_alert=False)

    await callback.message.edit_text(
        get_main_menu_text(callback.from_user.full_name),
        reply_markup=get_start_kb(user),
        parse_mode="HTML"
    )
    
    try:
        invite_link = await callback.bot.create_chat_invite_link(
            chat_id=config.PRIVATE_CHANNEL_ID,
            name=f"Trial_{callback.from_user.id}",
            creates_join_request=True
        )
        await callback.message.answer(
            f"🎉 <b>Пробный период успешно активирован!</b>\n\n"
            f"К вашему доступу добавлены <b>24 часа</b>.\n\n"
            f"Подайте заявку на вступление в закрытый канал по ссылке ниже. "
            f"Бот автоматически её одобрит.\n\n👉 {invite_link.invite_link}",
            parse_mode="HTML",
            reply_markup=get_close_button_kb()
        )
    except Exception as e:
        logger.error(f"Ошибка создания ссылки в канал: {e}")
        await callback.message.answer(
            "✅ Пробный период активирован!\n\n"
            "<i>(Ошибка: Бот не имеет прав администратора в закрытом канале для создания ссылки. "
            "Пожалуйста, сообщите администратору.)</i>",
            parse_mode="HTML",
            reply_markup=get_close_button_kb()
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
        await callback.message.answer(f"👉 Ваша ссылка для входа в канал:\n{invite_link.invite_link}",
        reply_markup=get_close_button_kb())
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка выдачи ссылки: {e}")
        await callback.answer("Ошибка получения ссылки. Бот не админ.", show_alert=True)

async def generate_status_text(listener, liq_aggregator, data_queue: asyncio.Queue) -> str:
    """Хелпер для генерации текста статуса (используется в команде и кнопке Обновить)"""
    stats = await MetricsService.get_system_stats(listener, liq_aggregator, data_queue)
    latency = MetricsService.get_analytics_latency(listener)

    active_pool = stats["active_connections"]
    total_pool = stats["total_connections"]

    status_emoji = "✅" if active_pool >= max(1, total_pool * 3 / 4) else "⚠️"
    if active_pool == 0: status_emoji = "❌"

    queue_size = stats["queue_size"]
    queue_status = "🟢" if queue_size < 50 else "🟡" if queue_size < 200 else "🔴"

    return (
        f"{status_emoji} {hbold('Система активна')}\n\n"
        f"🌐 Соединения: {hbold(active_pool)} / {hbold(total_pool)}\n"
        f"💓 Последний сигнал API: {hbold(latency)} назад\n\n"
        f"📡 Мониторинг пар: {hbold(stats['active_symbols'])}\n"
        f"🧠 Событий в кэше: {hbold(stats['total_events'])}\n"
        f"{queue_status} {hbold('Очередь обработки:')} {hbold(queue_size)}\n"
        f"📊 Нагрузка: CPU {hbold('{:.1f}'.format(stats['process_cpu_pct']))}% | RAM {hbold('{:.2f}'.format(stats['process_ram_pct']))}%\n\n"
        f"🕒 Время работы: {hbold(stats['uptime'])}\n"
        f"🕒 Время сервера: {stats['server_time']} UTC"
    )

@router.message(Command("status"))
async def cmd_status(message: types.Message, listener, liq_aggregator, data_queue: asyncio.Queue):
    """Вызов статуса через команду"""
    await message.delete()
    text = await generate_status_text(listener, liq_aggregator, data_queue)
    await message.answer(text, reply_markup=get_status_kb(), parse_mode="HTML")

@router.callback_query(F.data == "refresh_status")
async def process_refresh_status(callback: types.CallbackQuery, listener, liq_aggregator, data_queue: asyncio.Queue):
    """Обновление статуса по кнопке (меняет текст сообщения)"""
    text = await generate_status_text(listener, liq_aggregator, data_queue)
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
