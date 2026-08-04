import logging
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, InputMediaPhoto
from aiogram_i18n import I18nContext
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.models import User
from src.database.crud.user_service import apply_user_setting_preset, update_user_settings
from src.bot.keyboards import (
    get_back_to_settings_kb,
    get_preset_confirmation_kb,
    get_presets_selection_kb,
    get_settings_display_kb,
    get_settings_filters_kb,
    get_settings_kb,
    get_settings_rsi_kb,
)
from src.core.dto import SettingPresetId
from src.utils import format_smart_num, parse_numeric_input
from src.services import analyzer
from src.core.config import ImagePaths, config

logger = logging.getLogger(__name__)
router = Router()
PRESET_ORDER: tuple[SettingPresetId, ...] = ("SCALPER", "BALANCED", "CONSERVATIVE")

class SettingsStates(StatesGroup):
    waiting_for_threshold = State()
    waiting_for_cascade_threshold = State()
    waiting_for_oi_thresholds = State()
    waiting_for_mcap_pct = State()
    waiting_for_mcap_min_usd = State()
    waiting_for_mcap_cas_pct = State()
    waiting_for_mcap_cas_min_usd = State()
    waiting_for_rsi_thresholds = State()


def _format_preset_name(i18n: I18nContext, preset_id: SettingPresetId) -> str:
    return i18n.get(f"settings-preset-name-{preset_id.lower()}")


def _build_presets_catalog_caption(i18n: I18nContext) -> str:
    scalper = config.SETTING_PRESETS["SCALPER"]
    balanced = config.SETTING_PRESETS["BALANCED"]
    conservative = config.SETTING_PRESETS["CONSERVATIVE"]
    return i18n.get(
        "settings-preset-catalog-screen",
        scalper_mode=scalper.threshold_mode,
        scalper_threshold=format_smart_num(scalper.threshold),
        scalper_cascade=format_smart_num(scalper.threshold_cascade),
        scalper_oi_percent=format_smart_num(scalper.threshold_oi_percent, is_percent=True, decimal_places=1),
        scalper_oi_value=format_smart_num(scalper.threshold_oi_value),
        scalper_rsi_min=_format_rsi(scalper.rsi_min),
        scalper_rsi_max=_format_rsi(scalper.rsi_max),
        balanced_mode=balanced.threshold_mode,
        balanced_threshold=format_smart_num(balanced.threshold),
        balanced_cascade=format_smart_num(balanced.threshold_cascade),
        balanced_oi_percent=format_smart_num(balanced.threshold_oi_percent, is_percent=True, decimal_places=1),
        balanced_oi_value=format_smart_num(balanced.threshold_oi_value),
        balanced_rsi_min=_format_rsi(balanced.rsi_min),
        balanced_rsi_max=_format_rsi(balanced.rsi_max),
        conservative_mode=conservative.threshold_mode,
        conservative_threshold=format_smart_num(conservative.threshold),
        conservative_cascade=format_smart_num(conservative.threshold_cascade),
        conservative_oi_percent=format_smart_num(conservative.threshold_oi_percent, is_percent=True, decimal_places=1),
        conservative_oi_value=format_smart_num(conservative.threshold_oi_value),
        conservative_rsi_min=_format_rsi(conservative.rsi_min),
        conservative_rsi_max=_format_rsi(conservative.rsi_max),
    )


def _build_preset_confirmation_caption(i18n: I18nContext, preset_id: SettingPresetId) -> str:
    preset = config.SETTING_PRESETS[preset_id]
    return i18n.get(
        "settings-preset-confirm-screen",
        preset_name=_format_preset_name(i18n, preset_id),
        recommended_mode=preset.threshold_mode,
        threshold=format_smart_num(preset.threshold),
        threshold_cascade=format_smart_num(preset.threshold_cascade),
        threshold_mcap_pct=format_smart_num(preset.threshold_mcap_pct, is_percent=True, decimal_places=4),
        threshold_mcap_usd_min=format_smart_num(preset.threshold_mcap_usd_min),
        threshold_cascade_mcap_pct=format_smart_num(
            preset.threshold_cascade_mcap_pct, is_percent=True, decimal_places=4
        ),
        threshold_cascade_mcap_usd_min=format_smart_num(preset.threshold_cascade_mcap_usd_min),
        threshold_oi_percent=format_smart_num(preset.threshold_oi_percent, is_percent=True, decimal_places=1),
        threshold_oi_value=format_smart_num(preset.threshold_oi_value),
        rsi_min=_format_rsi(preset.rsi_min),
        rsi_max=_format_rsi(preset.rsi_max),
        preset_description=i18n.get(f"settings-preset-description-{preset_id.lower()}"),
    )


def _format_rsi(value: float) -> int:
    """Rounds RSI threshold to integer for display captions."""
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return 0


def _explain_rsi_profile(i18n: I18nContext, rsi_min: float, rsi_max: float) -> str:
    """Возвращает текстовый интерпретацию пресета RSI-гейта."""
    r_min = _format_rsi(rsi_min)
    r_max = _format_rsi(rsi_max)
    if r_min == 100 and r_max == 0:
        return i18n.get("settings-rsi-gate-explain-disabled")
    if r_min == 35 and r_max == 65:
        return i18n.get("settings-rsi-gate-explain-scalper")
    if r_min == 30 and r_max == 70:
        return i18n.get("settings-rsi-gate-explain-balanced")
    if r_min == 20 and r_max == 80:
        return i18n.get("settings-rsi-gate-explain-conservative")
    return i18n.get("settings-rsi-gate-explain-custom")


async def render_setting_presets_catalog(
    event: types.Message | types.CallbackQuery,
    i18n: I18nContext,
) -> None:
    await _render_settings_screen(
        event,
        _build_presets_catalog_caption(i18n),
        get_presets_selection_kb(),
        image_path=ImagePaths.SETTINGS,
    )


async def render_setting_preset_confirmation(
    event: types.Message | types.CallbackQuery,
    i18n: I18nContext,
    preset_id: SettingPresetId,
) -> None:
    await _render_settings_screen(
        event,
        _build_preset_confirmation_caption(i18n, preset_id),
        get_preset_confirmation_kb(preset_id),
        image_path=ImagePaths.SETTINGS,
    )


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
    await render_settings_filters_menu(callback, user, i18n)
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


def _build_settings_summary_caption(user: User, i18n: I18nContext) -> str:
    return i18n.get(
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
        rsi_min=str(_format_rsi(user.filter_rsi_min)),
        rsi_max=str(_format_rsi(user.filter_rsi_max)),
    )


def _build_settings_filters_caption(user: User, i18n: I18nContext) -> str:
    return i18n.get(
        "settings-filters-screen",
        threshold_mode=user.threshold_mode,
        threshold=format_smart_num(user.threshold),
        threshold_cascade=format_smart_num(user.threshold_cascade),
        threshold_mcap_pct=format_smart_num(user.threshold_mcap_pct, is_percent=True, decimal_places=4),
        threshold_mcap_usd_min=format_smart_num(user.threshold_mcap_usd_min),
        threshold_cascade_mcap_pct=format_smart_num(user.threshold_cascade_mcap_pct, is_percent=True, decimal_places=4),
        threshold_cascade_mcap_usd_min=format_smart_num(user.threshold_cascade_mcap_usd_min),
        threshold_oi_percent=format_smart_num(user.threshold_oi_percent, is_percent=True, decimal_places=1),
        threshold_oi_value=format_smart_num(user.threshold_oi_value),
        rsi_min=str(_format_rsi(user.filter_rsi_min)),
        rsi_max=str(_format_rsi(user.filter_rsi_max)),
    )


def _build_settings_rsi_caption(i18n: I18nContext) -> str:
    return i18n.get("settings-rsi-thresholds-prompt")


async def render_settings_rsi_menu(event: types.Message | types.CallbackQuery, i18n: I18nContext):
    """Подменю настройки RSI-гейта."""
    await _render_settings_screen(
        event,
        _build_settings_rsi_caption(i18n),
        get_settings_rsi_kb(),
        image_path=ImagePaths.SETTINGS,
    )


def _build_settings_display_caption(user: User, i18n: I18nContext) -> str:
    return i18n.get(
        "settings-display-screen"
    )


async def render_settings_menu(event: types.Message | types.CallbackQuery, user: User, i18n: I18nContext):
    """Корневой экран настроек."""
    await _render_settings_screen(
        event,
        _build_settings_summary_caption(user, i18n),
        get_settings_kb(user),
        image_path=ImagePaths.SETTINGS,
    )


async def render_settings_filters_menu(event: types.Message | types.CallbackQuery, user: User, i18n: I18nContext):
    """Подменю фильтров триггеров."""
    await _render_settings_screen(
        event,
        _build_settings_filters_caption(user, i18n),
        get_settings_filters_kb(user),
        image_path=ImagePaths.SETTINGS,
    )


async def render_settings_display_menu(event: types.Message | types.CallbackQuery, user: User, i18n: I18nContext):
    """Подменю отображения сообщения."""
    await _render_settings_screen(
        event,
        _build_settings_display_caption(user, i18n),
        get_settings_display_kb(user),
        image_path=ImagePaths.SETTINGS,
    )


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


@router.callback_query(F.data == "settings_filters")
async def process_open_settings_filters(callback: types.CallbackQuery, session: AsyncSession, i18n: I18nContext):
    user = await session.get(User, callback.from_user.id)
    if not user:
        return await callback.answer(i18n.get("settings-error-profile"), show_alert=True)
    await render_settings_filters_menu(callback, user, i18n)
    await callback.answer()


@router.callback_query(F.data == "settings_display")
async def process_open_settings_display(callback: types.CallbackQuery, session: AsyncSession, i18n: I18nContext):
    user = await session.get(User, callback.from_user.id)
    if not user:
        return await callback.answer(i18n.get("settings-error-profile"), show_alert=True)
    await render_settings_display_menu(callback, user, i18n)
    await callback.answer()


@router.callback_query(F.data == "open_setting_presets")
async def process_open_setting_presets(callback: types.CallbackQuery, session: AsyncSession, i18n: I18nContext):
    user = await session.get(User, callback.from_user.id)
    if not user:
        return await callback.answer(i18n.get("settings-error-profile"), show_alert=True)
    await render_setting_presets_catalog(callback, i18n)
    await callback.answer()


@router.callback_query(F.data.startswith("open_setting_preset_"))
async def process_open_setting_preset_confirmation(
    callback: types.CallbackQuery, session: AsyncSession, i18n: I18nContext
):
    user = await session.get(User, callback.from_user.id)
    if not user:
        return await callback.answer(i18n.get("settings-error-profile"), show_alert=True)

    preset_id = callback.data.removeprefix("open_setting_preset_").upper()
    if preset_id not in PRESET_ORDER:
        return await callback.answer(i18n.get("settings-save-error"), show_alert=True)

    await render_setting_preset_confirmation(callback, i18n, preset_id)
    await callback.answer()


@router.callback_query(F.data.startswith("apply_setting_preset_"))
async def process_apply_setting_preset(callback: types.CallbackQuery, session: AsyncSession, i18n: I18nContext):
    preset_id = callback.data.removeprefix("apply_setting_preset_").upper()
    if preset_id not in PRESET_ORDER:
        return await callback.answer(i18n.get("settings-save-error"), show_alert=True)

    user = await apply_user_setting_preset(session, callback.from_user.id, preset_id)
    if not user:
        return await callback.answer(i18n.get("settings-save-error"), show_alert=True)

    await render_settings_menu(callback, user, i18n)
    await callback.answer(
        i18n.get(
            "settings-preset-applied-toast",
            preset_name=_format_preset_name(i18n, preset_id),
        )
    )


@router.callback_query(F.data == "help_liq")
async def show_help_liq(callback: types.CallbackQuery, i18n: I18nContext):
    text = i18n.get("help-liquidations")
    await _render_settings_screen(callback, text, get_back_to_settings_kb("settings_filters"))
    await callback.answer()


@router.callback_query(F.data == "help_analytics")
async def show_help_analytics(callback: types.CallbackQuery, i18n: I18nContext):
    text = i18n.get("help-analytics")
    await _render_settings_screen(callback, text, get_back_to_settings_kb("settings_display"))
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
        if setting_type in {"cascade", "volume", "squeeze", "longs", "shorts"}:
            await render_settings_filters_menu(callback, user, i18n)
        else:
            await render_settings_display_menu(callback, user, i18n)
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


# ====== RSI-ГЕЙТ: НАСТРОЙКА ======

_RSI_PRESET_BAND_MAP = {
    "CONSERVATIVE": (20.0, 80.0),
    "BALANCED": (30.0, 70.0),
    "SCALPER": (35.0, 65.0),
    "DISABLED": (100.0, 0.0),
}


@router.callback_query(F.data == "menu_rsi_thresholds")
async def start_rsi_menu(
    callback: types.CallbackQuery, session: AsyncSession, i18n: I18nContext
):
    user = await session.get(User, callback.from_user.id)
    if not user:
        return await callback.answer(i18n.get("settings-error-profile"), show_alert=True)
    await render_settings_rsi_menu(callback, i18n)
    await callback.answer()


@router.callback_query(F.data.startswith("set_rsi_preset_"))
async def apply_rsi_preset(
    callback: types.CallbackQuery, session: AsyncSession, i18n: I18nContext
):
    preset_id = callback.data.removeprefix("set_rsi_preset_").upper()
    if preset_id not in _RSI_PRESET_BAND_MAP:
        return await callback.answer(i18n.get("settings-save-error"), show_alert=True)

    rsi_min, rsi_max = _RSI_PRESET_BAND_MAP[preset_id]
    user = await update_user_settings(
        session, callback.from_user.id, filter_rsi_min=rsi_min, filter_rsi_max=rsi_max
    )
    if not user:
        return await callback.answer(i18n.get("settings-save-error"), show_alert=True)

    await analyzer.invalidate_user_cache(callback.from_user.id)

    if rsi_min == 100.0 and rsi_max == 0.0:
        toast = i18n.get("settings-rsi-thresholds-disabled")
    else:
        toast = i18n.get(
            "settings-rsi-thresholds-updated",
            rsi_min=str(_format_rsi(rsi_min)),
            rsi_max=str(_format_rsi(rsi_max)),
            explain_text=_explain_rsi_profile(i18n, rsi_min, rsi_max),
        )
    await render_settings_filters_menu(callback, user, i18n)
    await callback.answer(toast, parse_mode="HTML")


@router.callback_query(F.data == "set_rsi_manual_start")
async def start_rsi_manual_input(
    callback: types.CallbackQuery, state: FSMContext, i18n: I18nContext
):
    await state.set_state(SettingsStates.waiting_for_rsi_thresholds)
    await callback.message.answer(
        i18n.get("settings-rsi-thresholds-prompt"), parse_mode="HTML"
    )
    await callback.answer()


@router.message(SettingsStates.waiting_for_rsi_thresholds)
async def process_rsi_thresholds(
    message: types.Message, state: FSMContext, session: AsyncSession
):
    i18n = I18nContext.get_current(no_error=False)
    parts = message.text.replace(",", " ").replace("/", " ").split()

    try:
        if len(parts) != 2:
            raise ValueError
        new_min = parse_numeric_input(parts[0])
        new_max = parse_numeric_input(parts[1])
        if new_min is None or new_max is None:
            raise ValueError
        if new_min < 0 or new_min > 100 or new_max < 0 or new_max > 100:
            raise ValueError
    except ValueError:
        return await message.answer(
            i18n.get("settings-rsi-thresholds-invalid"), parse_mode="HTML"
        )

    user = await update_user_settings(
        session, message.from_user.id, filter_rsi_min=float(new_min), filter_rsi_max=float(new_max)
    )
    if not user:
        await state.clear()
        return await message.answer(i18n.get("settings-save-error"))

    await analyzer.invalidate_user_cache(message.from_user.id)
    await state.clear()

    r_min = float(new_min)
    r_max = float(new_max)
    if r_min == 100.0 and r_max == 0.0:
        msg = i18n.get("settings-rsi-thresholds-disabled")
    else:
        msg = i18n.get(
            "settings-rsi-thresholds-updated",
            rsi_min=str(_format_rsi(r_min)),
            rsi_max=str(_format_rsi(r_max)),
            explain_text=_explain_rsi_profile(i18n, r_min, r_max),
        )
    await message.answer(msg, parse_mode="HTML")
