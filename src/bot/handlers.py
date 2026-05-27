import logging

from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.utils.markdown import hbold
from src.database.models import User
from src.database.session import async_session
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from src.bot.keyboards import get_settings_kb
from src.database.crud.user_service import get_or_create_user 

router = Router()


class SettingsStates(StatesGroup):
    waiting_for_threshold = State()
    waiting_for_cascade_threshold = State()
    waiting_for_oi_thresholds = State()

@router.callback_query(F.data == "ignore")
async def ignore_callback(callback: types.CallbackQuery):
    await callback.answer()

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
            f"Порог объема: {hbold(f'${user.threshold:,.0f}')}\n"
            f"Порог каскада: {hbold(f'${user.threshold_cascade:,.0f}')}\n")
        
        await message.delete()
        await message.answer(text, reply_markup=get_settings_kb(user), parse_mode="HTML")
        
@router.message(Command("status"))
async def cmd_status(
    message: types.Message, 
    listener,           # Aiogram автоматически прокинет сюда BybitListener
    liq_aggregator      # Aiogram автоматически прокинет сюда LiquidationAggregator
):
    from datetime import datetime, timezone

    await message.delete()

    active_symbols = len(liq_aggregator.history)
    total_in_mem = sum(len(d) for d in liq_aggregator.history.values())

    total_pool = len(listener.ws_connections)
    active_pool = listener.get_active_connections_count()

    status_emoji = "✅" if active_pool >= total_pool - 8 else "⚠️"
    if active_pool == 0: status_emoji = "❌"

    last_msg_str = "Никогда"
    if listener.last_message_time:
        diff = (datetime.now(timezone.utc).replace(tzinfo=None) - listener.last_message_time).total_seconds()
        last_msg_str = f"{int(diff)} сек. назад"
    
    text = (
        f"{status_emoji} {hbold('Система активна')}\n\n"
        f"🌐 Соединения: {hbold(active_pool)} / {hbold(total_pool)}\n"
        f"💓 Последний сигнал API: {hbold(last_msg_str)}\n"
        f"\n📡 Мониторинг пар: {hbold(active_symbols)}\n"
        f"\n🧠 Событий в кэше: {hbold(total_in_mem)}\n"
        f"\n🕒 Время сервера: {datetime.now(timezone.utc).replace(tzinfo=None).strftime('%H:%M:%S')} UTC"
    )
    await message.answer(text, parse_mode="HTML")

@router.callback_query(F.data == "close_message")
async def close_message(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.answer()

# === ХЕНДЛЕРЫ ДЛЯ ПОРОГА ОБЪЕМА ===
@router.callback_query(F.data == "set_threshold")
async def start_set_threshold(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите новый порог в долларах (число):")
    await state.set_state(SettingsStates.waiting_for_threshold)
    await callback.answer()


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

# === ХЕНДЛЕРЫ ДЛЯ ПОРОГА КАСКАДА ===
@router.callback_query(F.data == "set_cascade_threshold")
async def start_set_cascade_threshold(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите новый порог для КАСКАДОВ в долларах (число):")
    await state.set_state(SettingsStates.waiting_for_cascade_threshold)
    await callback.answer()

@router.message(SettingsStates.waiting_for_cascade_threshold)
async def process_cascade_threshold(message: types.Message, state: FSMContext):
    text = message.text.replace(',', '.')
    try:
        new_threshold = float(text)
    except ValueError:
        return await message.answer(
            "❌ Некорректный ввод!\n"
            "Пожалуйста, введите число (например: 5000 или 1000.5)"
        )
    
    if new_threshold <= 0:
        return await message.answer("❌ Число должно быть больше нуля. Попробуйте еще раз:")
    
    if new_threshold > 100_000_000_000:
        return await message.answer("❌ Слишком большое значение. Введите корректный порог:")
    
    try:
        async with async_session() as session:
            user = await session.get(User, message.from_user.id)
            if user:
                user.threshold_cascade = new_threshold
                await session.commit()
                await state.clear()
                await message.answer(f"✅ Порог каскадов успешно изменен на ${new_threshold:,.2f}!")
            else:
                await message.answer("❌ Ошибка: пользователь не найден в базе.")
                await state.clear()
    except Exception as e:
        logging.error(f"Ошибка при сохранении порога каскада: {e}")
        await message.answer("❌ Произошла ошибка при сохранении. Попробуйте позже.")
        await state.clear()

@router.callback_query(F.data.startswith("toggle_"))
async def toggle_settings(callback: types.CallbackQuery):
    setting_type = callback.data.replace("toggle_", "") 
    
    async with async_session() as session:
        user = await session.get(User, callback.from_user.id)
        
        # Stage 1
        if setting_type == "cascade":
            user.alert_cascade = not user.alert_cascade
        elif setting_type == "volume":
            user.alert_volume = not user.alert_volume
        elif setting_type == "squeeze":
            user.alert_squeeze = not user.alert_squeeze
        # Stage 2
        elif setting_type == "oi":
            user.alert_oi = not user.alert_oi
        elif setting_type == "rsi":
            user.alert_rsi = not user.alert_rsi
        elif setting_type == "cvd":
            user.alert_cvd = not user.alert_cvd
            
        await session.commit()
        await callback.message.edit_reply_markup(reply_markup=get_settings_kb(user))
        await callback.answer("Настройка сохранена")

@router.callback_query(F.data == "menu_oi_thresholds")
async def start_set_oi_thresholds(callback: types.CallbackQuery, state: FSMContext):
    text = (
        "📊 <b>Настройка порогов Открытого Интереса (OI)</b>\n\n"
        "Введите 2 числа через пробел:\n"
        "1. <b>Процент изменения</b> (например, 5.0)\n"
        "2. <b>Объем в долларах</b> (например, 500000)\n\n"
        "<i>Пример ввода:</i> <code>5.0 500000</code>"
    )
    await callback.message.answer(text, parse_mode="HTML")
    await state.set_state(SettingsStates.waiting_for_oi_thresholds)
    await callback.answer()

@router.message(SettingsStates.waiting_for_oi_thresholds)
async def process_oi_thresholds(message: types.Message, state: FSMContext):
    try:
        # Разбиваем сообщение на две части и заменяем запятые на точки
        parts = message.text.replace(',', '.').split()
        if len(parts) != 2:
            raise ValueError
        
        new_percent = float(parts[0])
        new_value = float(parts[1])
        
        if new_percent <= 0 or new_value <= 0:
            return await message.answer("❌ Числа должны быть больше нуля. Попробуйте еще раз:")
            
    except ValueError:
        return await message.answer(
            "❌ Некорректный ввод!\n"
            "Пожалуйста, введите два числа через пробел. Пример: 5.0 500000"
        )
    
    try:
        async with async_session() as session:
            user = await session.get(User, message.from_user.id)
            if user:
                user.threshold_oi_percent = new_percent
                user.threshold_oi_value = new_value
                await session.commit()
                await state.clear()
                
                formatted_value = f"${new_value/1_000_000:.1f}M" if new_value >= 1_000_000 else f"${new_value:,.0f}"
                await message.answer(f"✅ Пороги ОИ изменены!\nПроцент: <b>{new_percent}%</b>\nОбъем: <b>{formatted_value}</b>", parse_mode="HTML")
            else:
                await message.answer("❌ Ошибка: пользователь не найден.")
                await state.clear()
    except Exception as e:
        logging.error(f"Ошибка при сохранении порогов ОИ: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")
        await state.clear()