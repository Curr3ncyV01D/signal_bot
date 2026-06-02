import asyncio
from datetime import datetime, timezone
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.utils.markdown import hbold

from src.database.session import async_session
from src.database.crud.user_service import get_or_create_user

router = Router()

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    async with async_session() as session:
        await get_or_create_user(session, message.from_user.id, message.from_user.username)
    
    text = (
        f"👋 Добро пожаловать, {hbold(message.from_user.full_name)}!\n\n"
        f"Я профессиональный терминал для мониторинга ликвидаций на Bybit.\n"
        f"Я пришлю уведомление, когда на рынке начнется сильное движение.\n\n"
        f"Для вызова меню настроек используйте /settings"
    )
    await message.answer(text, parse_mode="HTML")

@router.message(Command("status"))
async def cmd_status(message: types.Message, listener, liq_aggregator, data_queue: asyncio.Queue):
    await message.delete()

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

    text = (
        f"{status_emoji} {hbold('Система активна')}\n\n"
        f"🌐 Соединения: {hbold(active_pool)} / {hbold(total_pool)}\n"
        f"💓 Последний сигнал API: {hbold(last_msg_str)}\n\n"
        f"📡 Мониторинг пар: {hbold(active_symbols)}\n"
        f"🧠 Событий в кэше: {hbold(total_in_mem)}\n"
        f"{queue_status} {hbold('Очередь обработки:')} {hbold(queue_size)}\n\n"
        f"🕒 Время сервера: {datetime.now(timezone.utc).replace(tzinfo=None).strftime('%H:%M:%S')} UTC"
    )
    await message.answer(text, parse_mode="HTML")