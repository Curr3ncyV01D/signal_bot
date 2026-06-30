import logging
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, InputMediaPhoto
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.models import User
from src.database.functions import get_utc_now
from src.database.crud.user_service import update_user_settings
from src.bot.keyboards import get_settings_kb, get_back_to_settings_kb, get_start_kb
from src.utils import format_smart_num, parse_numeric_input
from src.services import analyzer
from src.core.config import ImagePaths, config

logger = logging.getLogger(__name__)
router = Router()

class SettingsStates(StatesGroup):
    waiting_for_threshold = State()
    waiting_for_cascade_threshold = State()
    waiting_for_oi_thresholds = State()
    waiting_for_mcap_pct = State()
    waiting_for_mcap_min_usd = State()
    waiting_for_mcap_cas_pct = State()
    waiting_for_mcap_cas_min_usd = State()


@router.callback_query(F.data == "toggle_threshold_mode")
async def toggle_threshold_mode_handler(callback: types.CallbackQuery, session: AsyncSession):
    # Получаем текущего пользователя для инверсии режима
    user_obj = await session.get(User, callback.from_user.id)
    if not user_obj:
        return await callback.answer("Ошибка профиля", show_alert=True)
        
    new_mode = "PERCENT" if user_obj.threshold_mode == "USD" else "USD"
    
    # Обновляем через универсальный метод (pattern: ChannelService.update_settings)
    user = await update_user_settings(session, callback.from_user.id, threshold_mode=new_mode)
    if not user:
        return await callback.answer("Ошибка сохранения", show_alert=True)
    
    await analyzer.invalidate_user_cache()
    await callback.message.edit_reply_markup(reply_markup=get_settings_kb(user))
    await callback.answer(f"Режим изменен на {user.threshold_mode}")


@router.callback_query(F.data.in_(["set_mcap_pct", "set_mcap_min_usd", "set_mcap_cas_pct", "set_mcap_cas_min_usd"]))
async def set_mcap_parameter_start(callback: types.CallbackQuery, state: FSMContext):
    data = callback.data
    if data == "set_mcap_pct":
        await state.set_state(SettingsStates.waiting_for_mcap_pct)
        await callback.message.answer("Введите порог объема в % от капитализации (например, 0.005).\nРекомендуемое значение: 0.005%")
    elif data == "set_mcap_min_usd":
        await state.set_state(SettingsStates.waiting_for_mcap_min_usd)
        await callback.message.answer("Введите минимальный долларовый пол для режима % (например, 1000).")
    elif data == "set_mcap_cas_pct":
        await state.set_state(SettingsStates.waiting_for_mcap_cas_pct)
        await callback.message.answer("Введите порог каскада в % от капитализации (например, 0.01).\nРекомендуемое значение: 0.01%")
    elif data == "set_mcap_cas_min_usd":
        await state.set_state(SettingsStates.waiting_for_mcap_cas_min_usd)
        await callback.message.answer("Введите минимальный долларовый пол для каскада (например, 5000).")
    await callback.answer()


@router.message(SettingsStates.waiting_for_mcap_pct)
@router.message(SettingsStates.waiting_for_mcap_min_usd)
@router.message(SettingsStates.waiting_for_mcap_cas_pct)
@router.message(SettingsStates.waiting_for_mcap_cas_min_usd)
async def process_mcap_parameter(message: types.Message, state: FSMContext, session: AsyncSession):
    val = parse_numeric_input(message.text)
    if val is None or val < 0:
        return await message.answer("❌ Пожалуйста, введите положительное число.")

    current_state = await state.get_state()
    update_data = {}
    msg = ""

    if current_state == SettingsStates.waiting_for_mcap_pct:
        update_data["threshold_mcap_pct"] = val
        msg = f"✅ Порог объема установлен на {val}%"
    elif current_state == SettingsStates.waiting_for_mcap_min_usd:
        update_data["threshold_mcap_usd_min"] = val
        msg = f"✅ Мин. пол объема установлен на ${format_smart_num(val)}"
    elif current_state == SettingsStates.waiting_for_mcap_cas_pct:
        update_data["threshold_cascade_mcap_pct"] = val
        msg = f"✅ Порог каскада установлен на {val}%"
    elif current_state == SettingsStates.waiting_for_mcap_cas_min_usd:
        update_data["threshold_cascade_mcap_usd_min"] = val
        msg = f"✅ Мин. пол каскада установлен на ${format_smart_num(val)}"
            
    # Обновляем через универсальный метод (pattern: ChannelService.update_settings)
    user = await update_user_settings(session, message.from_user.id, **update_data)
    
    if user:
        await analyzer.invalidate_user_cache()
        await state.clear()
        await message.answer(msg)
    else:
        await message.answer("❌ Ошибка при сохранении настроек.")

async def _render_settings_screen(
    event: types.Message | types.CallbackQuery,
    caption: str,
    reply_markup=None,
    image_path: str | None = None
) -> None:
    """Умный рендеринг экранов настроек: с баннером или без него."""
    if image_path:
        photo = FSInputFile(image_path)
        if isinstance(event, types.Message):
            await event.answer_photo(
                photo=photo,
                caption=caption,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
            return

        try:
            await event.message.edit_media(
                media=InputMediaPhoto(
                    media=photo,
                    caption=caption,
                    parse_mode="HTML"
                ),
                reply_markup=reply_markup
            )
            return
        except Exception as e:
            await event.message.delete()
            await event.message.answer_photo(
                photo=photo,
                caption=caption,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
    else:
        if isinstance(event, types.Message):
            await event.answer(
                caption,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
            return

        try:
            await event.message.edit_text(
                caption,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
        except Exception as e:
            await event.message.delete()
            await event.message.answer(
                caption,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )


async def render_settings_menu(event: types.Message | types.CallbackQuery, user: User):
    """Единая функция для отрисовки меню настроек (из команды или кнопки 'Назад')"""
    now = get_utc_now()
    
    # Формируем статус подписки
    if user.subscription_end and user.subscription_end > now:
        sub_status = f"✅ Активна до {user.subscription_end.strftime('%d.%m.%Y %H:%M')} UTC"
    else:
        sub_status = "❌ Нет активной подписки"

    text = (
        f"<b>📊 Фильтры ликвидаций (Режим: {user.threshold_mode}):</b>\n"
        f"🔶 Порог объема: <b>${format_smart_num(user.threshold)}</b>\n"
        f"🔸 Порог каскада: <b>${format_smart_num(user.threshold_cascade)}</b>\n"
        f"🔷 Порог объема MCAP: <b>{user.threshold_mcap_pct}%</b> (мин. <b>${format_smart_num(user.threshold_mcap_usd_min)}</b>)\n"
        f"🔹 Порог каскада MCAP: <b>{user.threshold_cascade_mcap_pct}%</b> (мин. <b>${format_smart_num(user.threshold_cascade_mcap_usd_min)}</b>)\n\n"
        f"<b>📊 Фильтры аналитики (OI):</b>\n"
        f"📈 Мин. рост OI: <b>{format_smart_num(user.threshold_oi_percent, is_percent=True)}</b> и <b>${format_smart_num(user.threshold_oi_value)}</b>\n\n"
        f"💡 <i>Подсказка: Отключайте неинтересующие индикаторы ниже, чтобы сделать уведомления компактнее.</i>\n"
        f"\n<i>Нажмите на кнопки '❓ Справка', чтобы узнать подробности.</i>"
    )

    await _render_settings_screen(event, text, get_settings_kb(user), image_path=ImagePaths.SETTINGS)


@router.message(Command("settings"))
async def cmd_settings(message: types.Message, session: AsyncSession):
    await message.delete()
    user = await session.get(User, message.from_user.id)
    if not user:
        return await message.answer("❌ Ошибка при получении профиля. Нажмите /start")
    await render_settings_menu(message, user)


@router.callback_query(F.data == "open_settings")
async def process_open_settings(callback: types.CallbackQuery, session: AsyncSession):
    """Переход в настройки из главного меню"""
    user = await session.get(User, callback.from_user.id)
    if not user:
        return await callback.answer("Ошибка профиля", show_alert=True)
    await render_settings_menu(callback, user)
    await callback.answer()


@router.callback_query(F.data == "back_to_settings")
async def back_to_settings(callback: types.CallbackQuery, session: AsyncSession):
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
        "<i>Как применять:</i> Вход на локальных прострелах волатильности.\n\n"
        "<i>Остались вопросы по работе алгоритмов? Напишите нашему специалисту.</i>\n"
    )
    await _render_settings_screen(callback, text, get_back_to_settings_kb())
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
        "<i>Как применять:</i> RSI > 70 — актив перекуплен. В комбинации с ликвидацией шортов — сильнейший сигнал на разворот вниз.\n\n"
        "<i>Остались вопросы по работе алгоритмов? Напишите нашему специалисту.</i>\n"
    )
    await _render_settings_screen(callback, text, get_back_to_settings_kb())
    await callback.answer()


@router.callback_query(F.data.startswith("toggle_"))
async def toggle_settings(callback: types.CallbackQuery, session: AsyncSession):
    setting_type = callback.data.replace("toggle_", "") 
    
    # Получаем текущего пользователя для инверсии настройки
    user_obj = await session.get(User, callback.from_user.id)
    if not user_obj: return
    
    update_data = {}
    if setting_type == "cascade": update_data["alert_cascade"] = not user_obj.alert_cascade
    elif setting_type == "volume": update_data["alert_volume"] = not user_obj.alert_volume
    elif setting_type == "squeeze": update_data["alert_squeeze"] = not user_obj.alert_squeeze
    elif setting_type == "oi": update_data["alert_oi"] = not user_obj.alert_oi
    elif setting_type == "rsi": update_data["alert_rsi"] = not user_obj.alert_rsi
    elif setting_type == "cvd": update_data["alert_cvd"] = not user_obj.alert_cvd
    elif setting_type == "longs": update_data["alert_longs"] = not user_obj.alert_longs
    elif setting_type == "shorts": update_data["alert_shorts"] = not user_obj.alert_shorts
        
    # Обновляем через универсальный метод (pattern: ChannelService.update_settings)
    user = await update_user_settings(session, callback.from_user.id, **update_data)
    
    if user:
        # Сбрасываем кэш анализатора для мгновенного применения
        await analyzer.invalidate_user_cache()
        await callback.message.edit_reply_markup(reply_markup=get_settings_kb(user))
        await callback.answer("Настройка сохранена")

# === ЛИКВИДАЦИИ: НАСТРОЙКА ПОРОГОВ ===
@router.callback_query(F.data == "set_threshold")
async def start_set_threshold(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите новый порог объема в долларах (например: 5000):")
    await state.set_state(SettingsStates.waiting_for_threshold)
    await callback.answer()

@router.message(SettingsStates.waiting_for_threshold)
async def process_threshold(message: types.Message, state: FSMContext, session: AsyncSession):
    try:
        new_threshold = parse_numeric_input(message.text.replace("$", ""))
        if new_threshold <= 0 or new_threshold > 100_000_000_000:
            raise ValueError
    except ValueError:
        return await message.answer("❌ Пожалуйста, введите корректную сумму цифрами")
    
    # Обновляем через универсальный метод (pattern: ChannelService.update_settings)
    user = await update_user_settings(session, message.from_user.id, threshold=new_threshold)
    
    if user:
        await analyzer.invalidate_user_cache()
        await state.clear()
        await message.answer(f"✅ Порог объема изменен на <b>${format_smart_num(new_threshold)}</b>!", parse_mode="HTML")
    else:
        await message.answer("❌ Ошибка при сохранении настроек.")

@router.callback_query(F.data == "set_cascade_threshold")
async def start_set_cascade_threshold(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите порог для КАСКАДОВ в долларах (например: 2000):")
    await state.set_state(SettingsStates.waiting_for_cascade_threshold)
    await callback.answer()

@router.message(SettingsStates.waiting_for_cascade_threshold)
async def process_cascade_threshold(message: types.Message, state: FSMContext, session: AsyncSession):
    try:
        new_threshold = parse_numeric_input(message.text.replace("$", ""))
        if new_threshold <= 0 or new_threshold > 100_000_000_000:
            raise ValueError
    except ValueError:
        return await message.answer("❌ Пожалуйста, введите корректную сумму цифрами")
    
    # Обновляем через универсальный метод (pattern: ChannelService.update_settings)
    user = await update_user_settings(session, message.from_user.id, threshold_cascade=new_threshold)
    
    if user:
        await analyzer.invalidate_user_cache()
        await state.clear()
        await message.answer(f"✅ Порог каскадов изменен на <b>${format_smart_num(new_threshold)}</b>!", parse_mode="HTML")
    else:
        await message.answer("❌ Ошибка при сохранении настроек.")


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
async def process_oi_thresholds(message: types.Message, state: FSMContext, session: AsyncSession):
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
    
    # Обновляем через универсальный метод (pattern: ChannelService.update_settings)
    user = await update_user_settings(
        session, message.from_user.id, 
        threshold_oi_percent=new_pct, 
        threshold_oi_value=new_val
    )
    
    if user:
        await analyzer.invalidate_user_cache()
        await state.clear()
        await message.answer(
            f"✅ Пороги ОИ изменены!\nПроцент: <b>{format_smart_num(new_pct, is_percent=True)}</b>\nОбъем: <b>${format_smart_num(new_val)}</b>", 
            parse_mode="HTML"
        )
    else:
        await message.answer("❌ Ошибка при сохранении настроек.")
