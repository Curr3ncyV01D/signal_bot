import asyncio
import logging
from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.markdown import hbold

from src.bot.filters.admin import IsAdminFilter
from src.bot.keyboards.admin_broadcast_kb import (
    get_segment_selection_kb, 
    get_broadcast_confirm_kb
)
from src.bot.keyboards.admin_kb import get_admin_main_kb
from src.database.session import async_session
from src.database.crud.user_service import (
    get_all_receiver_ids, 
    get_vip_receiver_ids, 
    get_free_receiver_ids
)
from src.services.broadcast_service import run_broadcast

logger = logging.getLogger(__name__)

router = Router()
router.message.filter(IsAdminFilter())
router.callback_query.filter(IsAdminFilter())

class BroadcastStates(StatesGroup):
    waiting_for_segment = State()
    waiting_for_content = State()
    confirm_broadcast = State()

@router.callback_query(F.data == "admin_broadcast_start")
async def process_broadcast_start(callback: types.CallbackQuery, state: FSMContext):
    """Начало процесса создания рассылки - выбор сегмента"""
    await state.set_state(BroadcastStates.waiting_for_segment)
    text = (
        f"📣 {hbold('Создание рассылки')}\n\n"
        f"Выберите целевую группу пользователей:"
    )
    await callback.message.edit_text(text, reply_markup=get_segment_selection_kb(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(BroadcastStates.waiting_for_segment, F.data.startswith("broadcast_segment_"))
async def process_segment_selection(callback: types.CallbackQuery, state: FSMContext):
    """Сохранение выбранного сегмента и запрос контента"""
    segment = callback.data.replace("broadcast_segment_", "")
    await state.update_data(target_segment=segment)
    
    await state.set_state(BroadcastStates.waiting_for_content)
    
    segment_names = {"all": "Всем", "vip": "Только с подпиской", "free": "Только без подписки"}
    text = (
        f"🎯 Выбран сегмент: {hbold(segment_names.get(segment))}\n\n"
        f"Теперь пришлите сообщение, которое нужно разослать.\n"
        f"Бот скопирует его полностью: с текстом, медиа и кнопками."
    )
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()

@router.message(BroadcastStates.waiting_for_content)
async def process_broadcast_content(message: types.Message, state: FSMContext):
    """Захват контента рассылки и показ превью"""
    await state.update_data(
        from_chat_id=message.chat.id,
        message_id=message.message_id
    )
    
    await state.set_state(BroadcastStates.confirm_broadcast)
    
    # Отправляем само сообщение как превью
    await message.answer(f"👇 {hbold('ПРЕВЬЮ:')} Так будет выглядеть ваш пост. ПРОВЕРЬТЕ, ЧТО В ПОСТЕ НЕТ КОНФИДЕНЦИАЛЬНОЙ ИНФОРМАЦИИ",
                        parse_mode="HTML")
    await message.copy_to(chat_id=message.from_user.id)
    
    # Отправляем подтверждение
    await message.answer(
        "Подтверждаете запуск рассылки по выбранному сегменту?",
        reply_markup=get_broadcast_confirm_kb()
    )

@router.callback_query(F.data == "broadcast_confirm_start", BroadcastStates.confirm_broadcast)
async def process_broadcast_confirm(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    """Запуск рассылки в фоновом режиме"""
    data = await state.get_data()
    segment = data.get("target_segment")
    from_chat_id = data.get("from_chat_id")
    message_id = data.get("message_id")
    
    # Получаем список ID согласно сегменту
    async with async_session() as session:
        if segment == "all":
            user_ids = await get_all_receiver_ids(session)
        elif segment == "vip":
            user_ids = await get_vip_receiver_ids(session)
        else: # free
            user_ids = await get_free_receiver_ids(session)
            
    if not user_ids:
        await callback.message.answer("❌ Ошибка: В выбранном сегменте 0 пользователей.")
        await state.clear()
        return await callback.message.answer("Возврат в админку.", reply_markup=get_admin_main_kb())

    # Запускаем фоновую задачу
    asyncio.create_task(run_broadcast(bot, user_ids, from_chat_id, message_id, callback.from_user.id))
    
    # Расчет ориентировочного времени (25 сообщений в секунду + микропаузы)
    estimated_sec = int(len(user_ids) / 25)
    
    await callback.message.edit_text(
        f"🚀 {hbold('Рассылка запущена!')}\n\n"
        f"Цель: {hbold(len(user_ids))} пользователей.\n"
        f"По завершении вы получите детальный отчет.\n"
        f"⏳ Ориентировочное время: ~{hbold(estimated_sec)} сек.",
        parse_mode="HTML"
    )
    await state.clear()
    await callback.answer()

@router.callback_query(F.data == "broadcast_cancel")
async def process_broadcast_cancel(callback: types.CallbackQuery, state: FSMContext):
    """Отмена рассылки на любом этапе"""
    await state.clear()
    text = (
        "👑 <b>Панель администратора</b>\n\n"
        "Добро пожаловать! Здесь вы можете управлять пользователями, "
        "выдавать блокировки и проверять статусы подписок."
    )
    await callback.message.edit_text(
        text,
        reply_markup=get_admin_main_kb(),
        parse_mode="HTML"
    )
    await callback.answer("❌ <b>Создание рассылки отменено.</b>", show_alert=True)
