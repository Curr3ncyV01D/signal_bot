import logging
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from src.database.models import User
from src.database.session import async_session
from src.database.functions import get_utc_now
from src.bot.keyboards import get_settings_kb, get_back_to_settings_kb, get_start_kb
from src.utils import format_smart_num, parse_numeric_input
from src.services import analyzer

logger = logging.getLogger(__name__)
router = Router()

class SettingsStates(StatesGroup):
    waiting_for_threshold = State()
    waiting_for_cascade_threshold = State()
    waiting_for_oi_thresholds = State()

async def render_settings_menu(event: types.Message | types.CallbackQuery, user: User):
    """Единая функция для отрисовки меню настроек (из команды или кнопки 'Назад')"""
    now = get_utc_now()
    
    # Формируем статус подписки
    if user.subscription_end and user.subscription_end > now:
        sub_status = f"✅ Активна до {user.subscription_end.strftime('%d.%m.%Y %H:%M')} UTC"
    else:
        sub_status = "❌ Нет активной подписки"

    text = (
        f"⚙️ <b>Личный кабинет и настройки</b>\n\n"
        f"👑 <b>Подписка:</b> {sub_status}\n\n"
        f"<b>📊 Фильтры ликвидаций:</b>\n"
        f"🔸 Порог объема: <b>${format_smart_num(user.threshold)}</b>\n"
        f"🔸 Порог каскада: <b>${format_smart_num(user.threshold_cascade)}</b>\n\n"
        f"<b>📈 Фильтры аналитики (OI):</b>\n"
        f"🔸 Мин. рост OI: <b>{format_smart_num(user.threshold_oi_percent, is_percent=True)}</b> и <b>${format_smart_num(user.threshold_oi_value)}</b>\n\n"
        f"💡 <i>Подсказка: Отключайте неинтересующие индикаторы ниже, чтобы сделать уведомления компактнее.</i>\n"
        f"\n<i>Нажмите на кнопки '❓ Справка', чтобы узнать подробности.</i>"
    )
    markup = get_settings_kb(user)
    
    if isinstance(event, types.Message):
        await event.answer(text, reply_markup=markup, parse_mode="HTML")
    else:
        await event.message.edit_text(text, reply_markup=markup, parse_mode="HTML")

@router.message(Command("settings"))
async def cmd_settings(message: types.Message):
    await message.delete()
    async with async_session() as session:
        user = await session.get(User, message.from_user.id)
        if not user:
            return await message.answer("❌ Ошибка при получении профиля. Нажмите /start")
    await render_settings_menu(message, user)

@router.callback_query(F.data == "open_settings")
async def process_open_settings(callback: types.CallbackQuery):
    """Переход в настройки из главного меню"""
    async with async_session() as session:
        user = await session.get(User, callback.from_user.id)
        if not user:
            return await callback.answer("Ошибка профиля", show_alert=True)
    await render_settings_menu(callback, user)
    await callback.answer()

@router.callback_query(F.data == "back_to_settings")
async def back_to_settings(callback: types.CallbackQuery):
    async with async_session() as session:
        user = await session.get(User, callback.from_user.id)
        if not user:
            return await callback.message.answer("❌ Ошибка при получении профиля. Нажмите /start")
    await render_settings_menu(callback, user)
    await callback.answer()

@router.callback_query(F.data == "help_liq")
async def show_help_liq(callback: types.CallbackQuery):
    text = (
        "📊 <b>Справка: ЛИКВИДАЦИИ</b>\n\n"
        "Бот отслеживает принудительные закрытия позиций трейдеров (Margin Calls).\n\n"
        "⚡️ <b>Каскады:</b> Эффект «домино», когда одна ликвидация цепляет стопы других за 1-2 минуты.\n"
        "<i>Как применять:</i> Поиск экстремумов. Остановка каскада часто означает локальное дно или пик рынка.\n\n"
        "📊 <b>Объем:</b> Накопленная сумма ликвидаций за 1 час.\n"
        "<i>Как применять:</i> Показывает, кого глобально «бреют» на рынке.\n\n"
        "🔥 <b>Сквиз:</b> Резкий всплеск, когда 5-минутный объем почти равен часовому.\n"
        "<i>Как применять:</i> Вход на локальных прострелах волатильности."
    )
    await callback.message.edit_text(text, reply_markup=get_back_to_settings_kb(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "help_analytics")
async def show_help_analytics(callback: types.CallbackQuery):
    text = (
        "📈 <b>Справка: АНАЛИТИКА</b>\n\n"
        "Бот анализирует метрики, чтобы дать контекст движению цены.\n\n"
        "🟢 <b>Открытый интерес (OI):</b> Объем всех открытых фьючерсных позиций.\n"
        "<i>Как применять:</i> Если Цена растет + OI растет = в лонги заходят новые деньги (сильный тренд). Если Цена падает + OI падает = просто закрытие старых лонгов.\n\n"
        "📊 <b>CVD (Дельта):</b> Разница между рыночными покупками и продажами.\n"
        "<i>Как применять:</i> «More Buys» означает агрессию покупателей в моменте. Идеально для поиска точки входа.\n\n"
        "⚠️ <b>RSI (5m):</b> Индикатор перегретости актива.\n"
        "<i>Как применять:</i> RSI > 70 — актив перекуплен. В комбинации с ликвидацией шортов — сильнейший сигнал на разворот вниз."
    )
    await callback.message.edit_text(text, reply_markup=get_back_to_settings_kb(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("toggle_"))
async def toggle_settings(callback: types.CallbackQuery):
    setting_type = callback.data.replace("toggle_", "") 
    async with async_session() as session:
        user = await session.get(User, callback.from_user.id)
        if not user: return
        
        if setting_type == "cascade": user.alert_cascade = not user.alert_cascade
        elif setting_type == "volume": user.alert_volume = not user.alert_volume
        elif setting_type == "squeeze": user.alert_squeeze = not user.alert_squeeze
        elif setting_type == "oi": user.alert_oi = not user.alert_oi
        elif setting_type == "rsi": user.alert_rsi = not user.alert_rsi
        elif setting_type == "cvd": user.alert_cvd = not user.alert_cvd
        elif setting_type == "longs": user.alert_longs = not user.alert_longs
        elif setting_type == "shorts": user.alert_shorts = not user.alert_shorts
            
        await session.commit()
        # Сбрасываем кэш анализатора для мгновенного применения
        analyzer.invalidate_user_cache()
        
        await callback.message.edit_reply_markup(reply_markup=get_settings_kb(user))
        await callback.answer("Настройка сохранена")

# === ЛИКВИДАЦИИ: НАСТРОЙКА ПОРОГОВ ===
@router.callback_query(F.data == "set_threshold")
async def start_set_threshold(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите новый порог объема в долларах (например: 5000):")
    await state.set_state(SettingsStates.waiting_for_threshold)
    await callback.answer()

@router.message(SettingsStates.waiting_for_threshold)
async def process_threshold(message: types.Message, state: FSMContext):
    try:
        new_threshold = parse_numeric_input(message.text.replace("$", ""))
        if new_threshold <= 0 or new_threshold > 100_000_000_000:
            raise ValueError
    except ValueError:
        return await message.answer("❌ Пожалуйста, введите корректную сумму цифрами")
    
    try:
        async with async_session() as session:
            user = await session.get(User, message.from_user.id)
            user.threshold = new_threshold
            await session.commit()
            analyzer.invalidate_user_cache()
            await state.clear()
            await message.answer(f"✅ Порог объема изменен на <b>${format_smart_num(new_threshold)}</b>!", parse_mode="HTML")
    except Exception as e:
        logger.error(f"Ошибка сохранения: {e}")

@router.callback_query(F.data == "set_cascade_threshold")
async def start_set_cascade_threshold(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите порог для КАСКАДОВ в долларах (например: 2000):")
    await state.set_state(SettingsStates.waiting_for_cascade_threshold)
    await callback.answer()

@router.message(SettingsStates.waiting_for_cascade_threshold)
async def process_cascade_threshold(message: types.Message, state: FSMContext):
    try:
        new_threshold = parse_numeric_input(message.text.replace("$", ""))
        if new_threshold <= 0 or new_threshold > 100_000_000_000:
            raise ValueError
    except ValueError:
        return await message.answer("❌ Пожалуйста, введите корректную сумму цифрами")
    
    try:
        async with async_session() as session:
            user = await session.get(User, message.from_user.id)
            user.threshold_cascade = new_threshold
            await session.commit()
            analyzer.invalidate_user_cache()
            await state.clear()
            await message.answer(f"✅ Порог каскадов изменен на <b>${format_smart_num(new_threshold)}</b>!", parse_mode="HTML")
    except Exception as e:
        logger.error(f"Ошибка сохранения: {e}")

# === АНАЛИТИКА: НАСТРОЙКА ПОРОГОВ ОИ ===
@router.callback_query(F.data == "menu_oi_thresholds")
async def start_set_oi_thresholds(callback: types.CallbackQuery, state: FSMContext):
    text = (
        "📊 <b>Настройка порогов Открытого Интереса (OI)</b>\n\n"
        "Введите 2 числа через пробел:\n"
        "1. <b>Процент изменения</b> (например, 5.0)\n"
        "2. <b>Объем в долларах</b> (например, 500000)\n\n"
        "<i>Пример:</i> <code>5 500000</code>"
    )
    await callback.message.answer(text, parse_mode="HTML")
    await state.set_state(SettingsStates.waiting_for_oi_thresholds)
    await callback.answer()

@router.message(SettingsStates.waiting_for_oi_thresholds)
async def process_oi_thresholds(message: types.Message, state: FSMContext):
    parts = message.text.replace("%", "").replace("$", "").split()
    
    try:
        if len(parts) != 2:
            raise ValueError
        new_pct = parse_numeric_input(parts[0])
        new_val = parse_numeric_input(parts[1])
        if new_pct <= 0 or new_val <= 0:
            raise ValueError
    except ValueError:
        return await message.answer("❌ Пожалуйста, введите корректную сумму цифрами")
    
    try:
        async with async_session() as session:
            user = await session.get(User, message.from_user.id)
            user.threshold_oi_percent = new_pct
            user.threshold_oi_value = new_val
            await session.commit()
            analyzer.invalidate_user_cache()
            await state.clear()
            await message.answer(
                f"✅ Пороги ОИ изменены!\nПроцент: <b>{format_smart_num(new_pct, is_percent=True)}</b>\nОбъем: <b>${format_smart_num(new_val)}</b>", 
                parse_mode="HTML"
            )
    except Exception as e:
        logger.error(f"Ошибка сохранения ОИ: {e}")
