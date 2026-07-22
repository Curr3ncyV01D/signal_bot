import logging
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, InputMediaPhoto
from aiogram_i18n import I18nContext
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
async def toggle_threshold_mode_handler(callback: types.CallbackQuery, session: AsyncSession, i18n: I18nContext):
    # Получаем текущего пользователя для инверсии режима
    user_obj = await session.get(User, callback.from_user.id)
    if not user_obj:
        return await callback.answer(i18n.get("settings-error-profile"), show_alert=True)
        
    new_mode = "PERCENT" if user_obj.threshold_mode == "USD" else "USD"
    
    # Обновляем через универсальный метод (pattern: ChannelService.update_settings)
    user = await update_user_settings(session, callback.from_user.id, threshold_mode=new_mode)
    if not user:
        return await callback.answer(i18n.get("settings-error-save"), show_alert=True)
    
    await analyzer.invalidate_user_cache(callback.from_user.id)
    await callback.message.edit_reply_markup(reply_markup=get_settings_kb(user))
    await callback.answer(i18n.get("settings-mode-changed", mode=user.threshold_mode))


@router.callback_query(F.data.in_(["set_mcap_pct", "set_mcap_min_usd", "set_mcap_cas_pct", "set_mcap_cas_min_usd"]))
async def set_mcap_parameter_start(callback: types.CallbackQuery, state: FSMContext, i18n: I18nContext):
    data = callback.data
    if data == "set_mcap_pct":
        await state.set_state(SettingsStates.waiting_for_mcap_pct)
        await callback.message.answer(i18n.get("settings-enter-mcap-pct"))
    elif data == "set_mcap_min_usd":
        await state.set_state(SettingsStates.waiting_for_mcap_min_usd)
        await callback.message.answer(i18n.get("settings-enter-mcap-min-usd"))
    elif data == "set_mcap_cas_pct":
        await state.set_state(SettingsStates.waiting_for_mcap_cas_pct)
        await callback.message.answer(i18n.get("settings-enter-mcap-cascade-pct"))
    elif data == "set_mcap_cas_min_usd":
        await state.set_state(SettingsStates.waiting_for_mcap_cas_min_usd)
        await callback.message.answer(i18n.get("settings-enter-mcap-cascade-min-usd"))
    await callback.answer()


@router.message(SettingsStates.waiting_for_mcap_pct)
@router.message(SettingsStates.waiting_for_mcap_min_usd)
@router.message(SettingsStates.waiting_for_mcap_cas_pct)
@router.message(SettingsStates.waiting_for_mcap_cas_min_usd)
async def process_mcap_parameter(message: types.Message, state: FSMContext, session: AsyncSession):
    i18n = I18nContext.get_current(no_error=False)
    val = parse_numeric_input(message.text)
    if val is None or val < 0:
        return await message.answer(i18n.get("settings-positive-number-required"))

    current_state = await state.get_state()
    update_data = {}
    msg = ""

    if current_state == SettingsStates.waiting_for_mcap_pct:
        update_data["threshold_mcap_pct"] = val
        msg = i18n.get("settings-mcap-pct-updated", value=format_smart_num(val, is_percent=True, decimal_places=4))
    elif current_state == SettingsStates.waiting_for_mcap_min_usd:
        update_data["threshold_mcap_usd_min"] = val
        msg = i18n.get("settings-mcap-min-usd-updated", value=format_smart_num(val))
    elif current_state == SettingsStates.waiting_for_mcap_cas_pct:
        update_data["threshold_cascade_mcap_pct"] = val
        msg = i18n.get("settings-mcap-cascade-pct-updated", value=format_smart_num(val, is_percent=True, decimal_places=4))
    elif current_state == SettingsStates.waiting_for_mcap_cas_min_usd:
        update_data["threshold_cascade_mcap_usd_min"] = val
        msg = i18n.get("settings-mcap-cascade-min-usd-updated", value=format_smart_num(val))
            
    # Обновляем через универсальный метод (pattern: ChannelService.update_settings)
    user = await update_user_settings(session, message.from_user.id, **update_data)
    
    if user:
        await analyzer.invalidate_user_cache(message.from_user.id)
        await state.clear()
        await message.answer(msg)
    else:
        await message.answer(i18n.get("settings-save-error"))

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


async def render_settings_menu(event: types.Message | types.CallbackQuery, user: User, i18n: I18nContext):
    """Единая функция для отрисовки меню настроек (из команды или кнопки 'Назад')"""
    text = i18n.get(
        "settings-title",
        threshold_mode=user.threshold_mode,
        threshold=format_smart_num(user.threshold),
        threshold_cascade=format_smart_num(user.threshold_cascade),
        threshold_mcap_pct=format_smart_num(user.threshold_mcap_pct, is_percent=True, decimal_places=4),
        threshold_mcap_usd_min=format_smart_num(user.threshold_mcap_usd_min),
        threshold_cascade_mcap_pct=format_smart_num(user.threshold_cascade_mcap_pct, is_percent=True, decimal_places=4),
        threshold_cascade_mcap_usd_min=format_smart_num(user.threshold_cascade_mcap_usd_min),
        threshold_oi_percent=format_smart_num(user.threshold_oi_percent, is_percent=True, decimal_places=1),
        threshold_oi_value=format_smart_num(user.threshold_oi_value),
    )

    await _render_settings_screen(event, text, get_settings_kb(user), image_path=ImagePaths.SETTINGS)


@router.message(Command("settings"))
async def cmd_settings(message: types.Message, session: AsyncSession, i18n: I18nContext):
    await message.delete()
    user = await session.get(User, message.from_user.id)
    if not user:
        return await message.answer(i18n.get("settings-profile-error"))
    await render_settings_menu(message, user, i18n)


@router.callback_query(F.data == "open_settings")
async def process_open_settings(callback: types.CallbackQuery, session: AsyncSession, i18n: I18nContext):
    """Переход в настройки из главного меню"""
    user = await session.get(User, callback.from_user.id)
    if not user:
        return await callback.answer(i18n.get("settings-error-profile"), show_alert=True)
    await render_settings_menu(callback, user, i18n)
    await callback.answer()


@router.callback_query(F.data == "back_to_settings")
async def back_to_settings(callback: types.CallbackQuery, session: AsyncSession, i18n: I18nContext):
    user = await session.get(User, callback.from_user.id)
    if not user:
        return await callback.message.answer(i18n.get("settings-profile-error"))
    await render_settings_menu(callback, user, i18n)
    await callback.answer()


@router.callback_query(F.data == "help_liq")
async def show_help_liq(callback: types.CallbackQuery, i18n: I18nContext):
    text = i18n.get("help-liquidations")
    await _render_settings_screen(callback, text, get_back_to_settings_kb())
    await callback.answer()


@router.callback_query(F.data == "help_analytics")
async def show_help_analytics(callback: types.CallbackQuery, i18n: I18nContext):
    text = i18n.get("help-analytics")
    await _render_settings_screen(callback, text, get_back_to_settings_kb())
    await callback.answer()


@router.callback_query(F.data.startswith("toggle_"))
async def toggle_settings(callback: types.CallbackQuery, session: AsyncSession, i18n: I18nContext):
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
        await analyzer.invalidate_user_cache(callback.from_user.id)
        await callback.message.edit_reply_markup(reply_markup=get_settings_kb(user))
        await callback.answer(i18n.get("settings-saved"))

# === ЛИКВИДАЦИИ: НАСТРОЙКА ПОРОГОВ ===
@router.callback_query(F.data == "set_threshold")
async def start_set_threshold(callback: types.CallbackQuery, state: FSMContext, i18n: I18nContext):
    await callback.message.answer(i18n.get("settings-enter-threshold"))
    await state.set_state(SettingsStates.waiting_for_threshold)
    await callback.answer()

@router.message(SettingsStates.waiting_for_threshold)
async def process_threshold(message: types.Message, state: FSMContext, session: AsyncSession):
    i18n = I18nContext.get_current(no_error=False)
    try:
        new_threshold = parse_numeric_input(message.text.replace("$", ""))
        if new_threshold <= 0 or new_threshold > 100_000_000_000:
            raise ValueError
    except ValueError:
        return await message.answer(i18n.get("settings-invalid-amount"))
    
    # Обновляем через универсальный метод (pattern: ChannelService.update_settings)
    user = await update_user_settings(session, message.from_user.id, threshold=new_threshold)
    
    if user:
        await analyzer.invalidate_user_cache(message.from_user.id)
        await state.clear()
        await message.answer(
            i18n.get("settings-threshold-updated", value=format_smart_num(new_threshold)),
            parse_mode="HTML",
        )
    else:
        await message.answer(i18n.get("settings-save-error"))

@router.callback_query(F.data == "set_cascade_threshold")
async def start_set_cascade_threshold(callback: types.CallbackQuery, state: FSMContext, i18n: I18nContext):
    await callback.message.answer(i18n.get("settings-enter-cascade-threshold"))
    await state.set_state(SettingsStates.waiting_for_cascade_threshold)
    await callback.answer()

@router.message(SettingsStates.waiting_for_cascade_threshold)
async def process_cascade_threshold(message: types.Message, state: FSMContext, session: AsyncSession):
    i18n = I18nContext.get_current(no_error=False)
    try:
        new_threshold = parse_numeric_input(message.text.replace("$", ""))
        if new_threshold <= 0 or new_threshold > 100_000_000_000:
            raise ValueError
    except ValueError:
        return await message.answer(i18n.get("settings-invalid-amount"))
    
    # Обновляем через универсальный метод (pattern: ChannelService.update_settings)
    user = await update_user_settings(session, message.from_user.id, threshold_cascade=new_threshold)
    
    if user:
        await analyzer.invalidate_user_cache(message.from_user.id)
        await state.clear()
        await message.answer(
            i18n.get("settings-cascade-threshold-updated", value=format_smart_num(new_threshold)),
            parse_mode="HTML",
        )
    else:
        await message.answer(i18n.get("settings-save-error"))


# === АНАЛИТИКА: НАСТРОЙКА ПОРОГОВ ОИ ===
@router.callback_query(F.data == "menu_oi_thresholds")
async def start_set_oi_thresholds(callback: types.CallbackQuery, state: FSMContext, i18n: I18nContext):
    await callback.message.answer(i18n.get("settings-oi-thresholds-prompt"), parse_mode="HTML")
    await state.set_state(SettingsStates.waiting_for_oi_thresholds)
    await callback.answer()

@router.message(SettingsStates.waiting_for_oi_thresholds)
async def process_oi_thresholds(message: types.Message, state: FSMContext, session: AsyncSession):
    i18n = I18nContext.get_current(no_error=False)
    parts = message.text.replace("%", "").replace("$", "").split()
    
    try:
        if len(parts) != 2:
            raise ValueError
        new_pct = parse_numeric_input(parts[0])
        new_val = parse_numeric_input(parts[1])
        if new_pct <= 0 or new_val <= 0:
            raise ValueError
    except ValueError:
        return await message.answer(i18n.get("settings-invalid-amount"))
    
    # Обновляем через универсальный метод (pattern: ChannelService.update_settings)
    user = await update_user_settings(
        session, message.from_user.id, 
        threshold_oi_percent=new_pct, 
        threshold_oi_value=new_val
    )
    
    if user:
        await analyzer.invalidate_user_cache(message.from_user.id)
        await state.clear()
        await message.answer(
            i18n.get(
                "settings-oi-thresholds-updated",
                percent=format_smart_num(new_pct, is_percent=True),
                value=format_smart_num(new_val),
            ),
            parse_mode="HTML"
        )
    else:
        await message.answer(i18n.get("settings-save-error"))
