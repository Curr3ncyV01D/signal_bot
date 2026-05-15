from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.utils.markdown import hbold
from src.database.models import User
from src.database.crud import get_or_create_user
from src.database.session import async_session
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from src.bot.keyboards import get_settings_kb

router = Router()


class SettingsStates(StatesGroup):
    waiting_for_threshold = State()

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    async with async_session() as session:
        await get_or_create_user(session, message.from_user.id, message.from_user.username)
    
    await message.answer(f"Добро пожаловать, {message.from_user.full_name}! Я пришлю уведомление, когда на рынке начнется движение.\n\nДля вызова меню настроек используйте /settings")

@router.message(Command("settings"))
async def cmd_settings(message: types.Message):
    async with async_session() as session:
        # Если юзера нет, он будет создан
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username)
        
        if not user:
            await message.answer("Произошла ошибка при получении профиля. Нажмите /start")
            return

        text = (
            f"⚙️ {hbold('Ваши настройки')}\n\n"
            f"Текущий порог: {hbold(f'${user.threshold:,.0f}')}\n")
        
        await message.delete()
        await message.answer(text, reply_markup=get_settings_kb(user), parse_mode="HTML")
        
@router.message(Command("status"))
async def cmd_status(message: types.Message):
    from src.services.aggregator import aggregator
    from src.services.bybit_ws import bybit_listener
    from datetime import datetime, timezone

    await message.delete()

    active_symbols = len(aggregator.history)

    # Считаем общее кол-во ликвидаций в памяти
    total_in_mem = sum(len(d) for d in aggregator.history.values())

    # Считаем соединения
    # Проверяем, инициализирован ли листенер и есть ли у него список соединений
    conn_count = 0
    if bybit_listener and hasattr(bybit_listener, 'ws_connections'):
        conn_count = len(bybit_listener.ws_connections)
    
    text = (
        f"✅ {hbold('Система активна')}\n\n"
        f"📡 Мониторинг пар: {hbold(active_symbols)}\n"
        f"🧠 Событий в кэше: {hbold(total_in_mem)}\n"
        f"🌐 Соединений (Pool): {hbold(conn_count)}\n"
        f"🕒 Время сервера: {datetime.now(timezone.utc).replace(tzinfo=None).strftime('%H:%M:%S')} UTC"
    )
    await message.answer(text, parse_mode="HTML")

@router.callback_query(F.data == "close_message")
async def close_message(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.answer()

@router.callback_query(F.data == "set_threshold")
async def start_set_threshold(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите новый порог в долларах (число):")
    await state.set_state(SettingsStates.waiting_for_threshold)
    await callback.answer()

# Обработка введенного числа
@router.message(SettingsStates.waiting_for_threshold)
async def process_threshold(message: types.Message, state: FSMContext):
    text = message.text.replace(',', '.')
    try:
        new_threshold = float(text)
    except ValueError:
        return await message.answer(
            "❌ Некорректный ввод!\n\n"
            "Пожалуйста, введите число (целое или десятичное через точку).\n"
            "Например: 50000 или 1000.5"
        )
    
    if new_threshold <= 0:
        return await message.answer("❌ Число должно быть строго больше нуля. Попробуйте еще раз:")
    
    if new_threshold > 100_000_000_000:
        return await message.answer("❌ Слишком большое значение (макс. 100 млрд). Введите корректный порог:")
    
    try:
        async with async_session() as session:
            user = await session.get(User, message.from_user.id)
            if user:
                user.threshold = new_threshold
                await session.commit()
                await state.clear()
                await message.answer(f"✅ Порог успешно изменен на ${new_threshold:,.2f}!")
            else:
                await message.answer("❌ Ошибка: пользователь не найден в базе.")
                await state.clear()
    except Exception as e:
        logging.error(f"Ошибка при сохранении порога: {e}")
        await message.answer("❌ Произошла ошибка при сохранении в базу данных. Попробуйте позже.")
        await state.clear()

@router.callback_query(F.data.startswith("toggle_"))
async def toggle_settings(callback: types.CallbackQuery):
    # Извлекаем опцию настройки уведомления из callback_data
    setting_type = callback.data.replace("toggle_", "") 
    
    async with async_session() as session:
        user = await session.get(User, callback.from_user.id)
        
        # Инвертируем выбранную настройку
        if setting_type == "cascade":
            user.alert_cascade = not user.alert_cascade
        elif setting_type == "volume":
            user.alert_volume = not user.alert_volume
        elif setting_type == "squeeze":
            user.alert_squeeze = not user.alert_squeeze
            
        await session.commit()
        
        # Обновляем только кнопки, не переотправляя сообщение
        await callback.message.edit_reply_markup(reply_markup=get_settings_kb(user))
        await callback.answer("Настройка сохранена")