import logging

from aiogram import F, Router, types
from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram_i18n import I18nContext
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import ImagePaths, config
from src.core.dto import SettingPresetId
from src.core.localization import normalize_locale_code
from src.core.redis_bus import redis_bus
from src.database.crud import billing_service
from src.database.crud.user_service import (
    activate_trial,
    apply_user_setting_preset,
    complete_user_setup,
    get_or_create_user,
    is_user_vip,
)
from src.database.models import User
from src.services.logic.analyzer import invalidate_user_cache
from src.utils import format_smart_num

logger = logging.getLogger(__name__)
router = Router()
PRESET_ORDER: tuple[SettingPresetId, ...] = ("SCALPER", "BALANCED", "CONSERVATIVE")


def get_onboarding_language_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Русский", callback_data="onboarding_language_ru"),
        InlineKeyboardButton(text="English", callback_data="onboarding_language_en"),
    )
    return builder.as_markup()


async def render_onboarding_language_screen(
    event: types.Message | types.CallbackQuery,
    i18n: I18nContext,
) -> None:
    """Показывает первый экран онбординга с выбором языка."""
    caption = i18n.get("onboarding-language-screen")
    reply_markup = get_onboarding_language_kb()
    photo = FSInputFile(ImagePaths.WELCOME)

    if isinstance(event, types.Message):
        await event.answer_photo(
            photo=photo,
            caption=caption,
            reply_markup=reply_markup,
            parse_mode="HTML",
        )
        return

    try:
        await event.message.edit_media(
            media=InputMediaPhoto(
                media=photo,
                caption=caption,
                parse_mode="HTML",
            ),
            reply_markup=reply_markup,
        )
    except Exception as exc:
        logger.warning(f"Не удалось показать onboarding через edit_media: {exc}")
        try:
            await event.message.delete()
        except Exception:
            pass
        await event.message.answer_photo(
            photo=FSInputFile(ImagePaths.WELCOME),
            caption=caption,
            reply_markup=reply_markup,
            parse_mode="HTML",
        )


def get_presets_selection_kb(i18n: I18nContext) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=i18n.get("onboarding-preset-button-scalper"),
            callback_data="apply_onboarding_preset_SCALPER",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=i18n.get("onboarding-preset-button-balanced"),
            callback_data="apply_onboarding_preset_BALANCED",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=i18n.get("onboarding-preset-button-conservative"),
            callback_data="apply_onboarding_preset_CONSERVATIVE",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=i18n.get("onboarding-preset-button-skip"),
            callback_data="skip_onboarding_preset",
        )
    )
    return builder.as_markup()


def _build_presets_selection_caption(i18n: I18nContext) -> str:
    scalper = config.SETTING_PRESETS["SCALPER"]
    balanced = config.SETTING_PRESETS["BALANCED"]
    conservative = config.SETTING_PRESETS["CONSERVATIVE"]
    return i18n.get(
        "onboarding-presets-screen",
        scalper_mode=scalper.threshold_mode,
        scalper_threshold=format_smart_num(scalper.threshold),
        scalper_cascade=format_smart_num(scalper.threshold_cascade),
        scalper_oi_percent=format_smart_num(scalper.threshold_oi_percent, is_percent=True, decimal_places=1),
        scalper_oi_value=format_smart_num(scalper.threshold_oi_value),
        balanced_mode=balanced.threshold_mode,
        balanced_threshold=format_smart_num(balanced.threshold),
        balanced_cascade=format_smart_num(balanced.threshold_cascade),
        balanced_oi_percent=format_smart_num(balanced.threshold_oi_percent, is_percent=True, decimal_places=1),
        balanced_oi_value=format_smart_num(balanced.threshold_oi_value),
        conservative_mode=conservative.threshold_mode,
        conservative_threshold=format_smart_num(conservative.threshold),
        conservative_cascade=format_smart_num(conservative.threshold_cascade),
        conservative_oi_percent=format_smart_num(conservative.threshold_oi_percent, is_percent=True, decimal_places=1),
        conservative_oi_value=format_smart_num(conservative.threshold_oi_value),
    )


async def render_presets_selection_screen(
    event: types.Message | types.CallbackQuery,
    i18n: I18nContext,
) -> None:
    """Показывает шаг выбора профиля стратегии с возможностью пропуска."""
    caption = _build_presets_selection_caption(i18n)
    reply_markup = get_presets_selection_kb(i18n)
    photo = FSInputFile(ImagePaths.SETTINGS)

    if isinstance(event, types.Message):
        await event.answer_photo(
            photo=photo,
            caption=caption,
            reply_markup=reply_markup,
            parse_mode="HTML",
        )
        return

    try:
        await event.message.edit_media(
            media=InputMediaPhoto(
                media=photo,
                caption=caption,
                parse_mode="HTML",
            ),
            reply_markup=reply_markup,
        )
    except Exception as exc:
        logger.warning(f"Не удалось показать выбор пресетов через edit_media: {exc}")
        try:
            await event.message.delete()
        except Exception:
            pass
        await event.message.answer_photo(
            photo=FSInputFile(ImagePaths.SETTINGS),
            caption=caption,
            reply_markup=reply_markup,
            parse_mode="HTML",
        )


def _is_community_bonus_available() -> bool:
    return config.COMMUNITY_GROUP_ID is not None and bool(config.COMMUNITY_GROUP_LINK)


def _resolve_onboarding_step(user: User) -> str:
    step = str(getattr(user, "onboarding_step", "LANGUAGE") or "LANGUAGE")
    if step == "COMMUNITY_BONUS" and (not _is_community_bonus_available() or user.is_community_bonus_used):
        return "PRESET_SELECTION"
    if step not in {"LANGUAGE", "COMMUNITY_BONUS", "PRESET_SELECTION", "COMPLETED"}:
        return "LANGUAGE"
    return step


async def render_pending_onboarding_screen(
    event: types.Message | types.CallbackQuery,
    user: User,
    i18n: I18nContext,
) -> None:
    """Рендерит актуальный шаг незавершенного онбординга."""
    step = _resolve_onboarding_step(user)
    if step == "COMMUNITY_BONUS":
        await render_community_bonus_screen(event, i18n, show_back_to_main=False)
        return
    if step == "PRESET_SELECTION":
        await render_presets_selection_screen(event, i18n)
        return
    await render_onboarding_language_screen(event, i18n)


def get_community_bonus_kb(
    i18n: I18nContext,
    *,
    show_back_to_main: bool,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=i18n.get("community-bonus-button-join"),
            url=config.COMMUNITY_GROUP_LINK,
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=i18n.get("community-bonus-button-verify"),
            callback_data="verify_community_join",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=i18n.get("main-button-home") if show_back_to_main else i18n.get("community-bonus-button-later"),
            callback_data="back_to_main" if show_back_to_main else "dismiss_community_bonus",
        )
    )
    return builder.as_markup()


async def render_community_bonus_screen(
    event: types.Message | types.CallbackQuery,
    i18n: I18nContext,
    *,
    show_back_to_main: bool,
) -> None:
    """Показывает оффер на бонус за вступление в сообщество."""
    caption = i18n.get("community-bonus-screen", hours=config.COMMUNITY_BONUS_HOURS)
    reply_markup = get_community_bonus_kb(i18n, show_back_to_main=show_back_to_main)
    photo = FSInputFile(ImagePaths.WELCOME)

    if isinstance(event, types.Message):
        await event.answer_photo(
            photo=photo,
            caption=caption,
            reply_markup=reply_markup,
            parse_mode="HTML",
        )
        return

    try:
        await event.message.edit_media(
            media=InputMediaPhoto(
                media=photo,
                caption=caption,
                parse_mode="HTML",
            ),
            reply_markup=reply_markup,
        )
    except Exception as exc:
        logger.warning(f"Не удалось показать community bonus через edit_media: {exc}")
        try:
            await event.message.delete()
        except Exception:
            pass
        await event.message.answer_photo(
            photo=FSInputFile(ImagePaths.WELCOME),
            caption=caption,
            reply_markup=reply_markup,
            parse_mode="HTML",
        )


@router.callback_query(F.data.startswith("onboarding_language_"))
async def process_onboarding_language(
    callback: types.CallbackQuery,
    session: AsyncSession,
    i18n: I18nContext,
) -> None:
    """Сохраняет выбранный язык и переводит пользователя на следующий шаг мастера."""
    selected_locale = normalize_locale_code(callback.data.rsplit("_", 1)[-1])
    user = await get_or_create_user(
        session,
        callback.from_user.id,
        callback.from_user.username,
        telegram_language_code=selected_locale,
    )
    if user is None:
        await callback.answer(i18n.get("settings-error-profile"), show_alert=True)
        return

    user.language_code = selected_locale
    user.onboarding_step = (
        "COMMUNITY_BONUS"
        if _is_community_bonus_available() and not user.is_community_bonus_used
        else "PRESET_SELECTION"
    )
    try:
        await session.commit()
        await session.refresh(user)
    except Exception as exc:
        await session.rollback()
        logger.error("Не удалось сохранить шаг онбординга для %s: %s", user.id, exc)
        await callback.answer(i18n.get("settings-error-save"), show_alert=True)
        return

    await invalidate_user_cache(user.id)

    with i18n.use_locale(selected_locale):
        await render_pending_onboarding_screen(callback, user, i18n)
        await callback.answer(i18n.get("onboarding-language-selected"))


@router.callback_query(F.data == "dismiss_community_bonus")
async def process_dismiss_community_bonus(
    callback: types.CallbackQuery,
    session: AsyncSession,
    i18n: I18nContext,
) -> None:
    user = await session.get(User, callback.from_user.id)
    if not user:
        await callback.answer(i18n.get("profile-not-found-start"), show_alert=True)
        return

    user.onboarding_step = "PRESET_SELECTION"
    try:
        await session.commit()
        await session.refresh(user)
    except Exception as exc:
        await session.rollback()
        logger.error("Не удалось перевести пользователя %s на выбор пресета: %s", user.id, exc)
        await callback.answer(i18n.get("settings-error-save"), show_alert=True)
        return

    await render_presets_selection_screen(callback, i18n)
    await callback.answer(i18n.get("community-bonus-later-toast"))


@router.callback_query(F.data == "open_community_bonus")
async def process_open_community_bonus(
    callback: types.CallbackQuery,
    session: AsyncSession,
    i18n: I18nContext,
) -> None:
    user = await session.get(User, callback.from_user.id)
    if not user:
        await callback.answer(i18n.get("profile-not-found-start"), show_alert=True)
        return

    if user.is_community_bonus_used:
        await callback.answer(i18n.get("community-bonus-already-used"), show_alert=True)
        return

    if not _is_community_bonus_available():
        await callback.answer(i18n.get("community-bonus-unavailable"), show_alert=True)
        return

    await render_community_bonus_screen(callback, i18n, show_back_to_main=True)
    await callback.answer()


_GATE_ALLOWED_MEMBER_STATUSES = {"member", "administrator", "creator", "restricted"}


async def _verify_gate_resources_membership(bot, user_id: int) -> tuple[bool, bool]:
    """
    Проверяет членство пользователя в ОБОИХ ресурсах: новостном канале + чат сообщества.
    Если ресурс не задан — считает его выполненным.
    Возвращает кортеж (is_community_member_only, is_gate_approved):
      - is_community_member_only: True если в COMMUNITY_GROUP_ID пользователь есть (для бонуса)
      - is_gate_approved: True если в ОБОИХ ресурсах пользователь есть (для Gatekeeper)
    При любой ошибке API возвращает (False, False).
    """
    is_community_ok: bool = False
    is_news_ok: bool = True

    if config.NEWS_CHANNEL_ID:
        try:
            member = await bot.get_chat_member(config.NEWS_CHANNEL_ID, user_id)
            status = getattr(member, "status", None)
            is_news_ok = bool(status in _GATE_ALLOWED_MEMBER_STATUSES)
        except Exception as exc:
            logger.warning(
                "Не удалось проверить участие пользователя %s в news_channel: %s",
                user_id, exc,
            )
            return False, False

    if config.COMMUNITY_GROUP_ID:
        try:
            member = await bot.get_chat_member(config.COMMUNITY_GROUP_ID, user_id)
            status = getattr(member, "status", None)
            is_community_ok = bool(status in _GATE_ALLOWED_MEMBER_STATUSES)
        except Exception as exc:
            logger.warning(
                "Не удалось проверить участие пользователя %s в community: %s",
                user_id, exc,
            )
            return False, False
    else:
        is_community_ok = True

    gate_approved = is_news_ok and is_community_ok
    return is_community_ok, gate_approved


async def _update_gate_status_and_answer(
    callback: types.CallbackQuery,
    i18n: I18nContext,
    gate_approved: bool,
) -> None:
    """Обновляет Redis gate status и отвечает на callback алертом."""
    try:
        await redis_bus.set_gate_status(
            int(callback.from_user.id),
            gate_approved,
            ttl=config.GATE_CACHE_TTL_SEC,
        )
    except Exception:
        logger.exception(
            "Ошибка записи gate status в Redis user_id=%s gate=%s",
            callback.from_user.id, gate_approved,
        )

    key = "gate-subscription-verified" if gate_approved else "gate-subscription-not-found"
    await callback.answer(i18n.get(key), show_alert=True)


@router.callback_query(F.data.in_({"verify_community_join", "verify_gate_sub"}))
async def process_verify_gate_subscription(
    callback: types.CallbackQuery,
    session: AsyncSession,
    i18n: I18nContext,
) -> None:
    """
    Универсальный обработчик ручной проверки членства в медиа-ресурсах:
      - verify_community_join: экран бонус-оффера (проверяет + бонус + gate)
      - verify_gate_sub: кнопка «Проверить подписку» из Bouncer-уведомления (только gate)
    """
    action = str(callback.data)

    # 1. Универсальная проверка обоих ресурсов + обновление gate status в Redis
    is_community_member, gate_approved = await _verify_gate_resources_membership(
        callback.bot, callback.from_user.id,
    )

    user = await session.get(User, callback.from_user.id)
    if not user:
        await callback.answer(i18n.get("profile-not-found-start"), show_alert=True)
        return

    # 2. Если пользователь пришел с экрана community bonus: оригинальная логика применения бонуса
    if action == "verify_community_join":
        if not _is_community_bonus_available():
            # Бонус недоступен (ресурс отключен в конфиге) → отвечаем только gate-статусом
            await _update_gate_status_and_answer(callback, i18n, gate_approved)
            return

        if user.is_community_bonus_used:
            await _update_gate_status_and_answer(callback, i18n, gate_approved)
            return

        if not is_community_member:
            # Оригинальное сообщение о необходимости вступления именно в community
            try:
                await redis_bus.set_gate_status(
                    int(callback.from_user.id),
                    False,
                    ttl=config.GATE_CACHE_TTL_SEC,
                )
            except Exception:
                pass
            await callback.answer(i18n.get("community-bonus-join-required"), show_alert=True)
            return

        # Пользователь в community — применяем бонус и переводим на следующий шаг онбординга
        success, _ = await billing_service.apply_community_bonus(session, callback.from_user.id)
        if not success:
            await session.rollback()
            await _update_gate_status_and_answer(callback, i18n, gate_approved)
            return

        user.onboarding_step = "PRESET_SELECTION"
        try:
            await session.commit()
            await session.refresh(user)
        except Exception:
            await session.rollback()
            await _update_gate_status_and_answer(callback, i18n, gate_approved)
            return

        await _update_gate_status_and_answer(callback, i18n, gate_approved)
        # После успешного подтверждения бонуса — идем дальше на выбор пресета
        # (если мы на экране онбординга, а не в диалоге после Bouncer)
        if _resolve_onboarding_step(user) == "PRESET_SELECTION":
            await render_presets_selection_screen(callback, i18n)
        return

    # 3. verify_gate_sub или любой другой алиас — только gate-проверка, нет шагов онбординга
    await _update_gate_status_and_answer(callback, i18n, gate_approved)
    # После ручной верификации — показываем обновлённое главное меню (Clean State Model).
    # Пользователь, только что подтвердивший членство, автоматом попадает в STATE_FREE_ACTIVE
    # (или STATE_VIP_ACTIVE если уже купил) с актуальной CTA-кнопкой.
    try:
        if callback.message is not None:
            from src.bot.handlers.commands import render_main_menu

            assert user is not None, "user expected to be fetched earlier"
            await render_main_menu(
                callback,
                user,
                callback.from_user.full_name,
                i18n,
            )
    except Exception as exc:
        logger.warning(
            "Не удалось перерисовать главное меню после verify_gate_sub user=%s: %s",
            callback.from_user.id,
            exc,
        )
        # Graceful fallback: убираем старую gate-клавиатуру если не смогли нарисовать новую
        try:
            if (
                callback.message
                and getattr(callback.message, "reply_markup", None) is not None
            ):
                await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
    return


@router.callback_query(F.data.startswith("apply_onboarding_preset_"))
async def process_apply_onboarding_preset(
    callback: types.CallbackQuery,
    session: AsyncSession,
    i18n: I18nContext,
) -> None:
    preset_id = callback.data.removeprefix("apply_onboarding_preset_").upper()
    if preset_id not in PRESET_ORDER:
        await callback.answer(i18n.get("settings-error-save"), show_alert=True)
        return

    user = await session.get(User, callback.from_user.id)
    if user is None:
        await callback.answer(i18n.get("profile-not-found-start"), show_alert=True)
        return

    user_with_preset = await apply_user_setting_preset(session, callback.from_user.id, preset_id)
    if user_with_preset is None:
        await callback.answer(i18n.get("settings-error-save"), show_alert=True)
        return

    if not user.is_trial_used:
        activated, _ = await activate_trial(session, callback.from_user.id)
        if activated:
            _, _ = await billing_service.issue_bonus_subscription(
                session=session,
                user_id=callback.from_user.id,
                hours=config.TRIAL_DURATION_DAYS * 24,
                internal_description="billing-tx-trial-description",
                locale=user.language_code,
            )
            try:
                await session.commit()
            except Exception:
                await session.rollback()
                logger.error(
                    "Не удалось закоммитить триал в онбординге пользователя %s",
                    callback.from_user.id,
                )
        await invalidate_user_cache(callback.from_user.id)

    completed_user = await complete_user_setup(session, callback.from_user.id)
    if completed_user is None:
        await callback.answer(i18n.get("settings-error-save"), show_alert=True)
        return

    await invalidate_user_cache(callback.from_user.id)

    from src.bot.handlers.commands import render_main_menu

    await render_main_menu(callback, completed_user, callback.from_user.full_name, i18n)
    await callback.answer(
        i18n.get(
            f"onboarding-preset-applied-{preset_id.lower()}",
        )
    )


@router.callback_query(F.data == "skip_onboarding_preset")
async def process_skip_onboarding_preset(
    callback: types.CallbackQuery,
    session: AsyncSession,
    i18n: I18nContext,
) -> None:
    user = await session.get(User, callback.from_user.id)
    if user is None:
        await callback.answer(i18n.get("profile-not-found-start"), show_alert=True)
        return

    if not user.is_trial_used:
        activated, _ = await activate_trial(session, callback.from_user.id)
        if activated:
            _, _ = await billing_service.issue_bonus_subscription(
                session=session,
                user_id=callback.from_user.id,
                hours=config.TRIAL_DURATION_DAYS * 24,
                internal_description="billing-tx-trial-description",
                locale=user.language_code,
            )
            try:
                await session.commit()
            except Exception:
                await session.rollback()
                logger.error(
                    "Не удалось закоммитить триал при skip онбординга пользователя %s",
                    callback.from_user.id,
                )
        await invalidate_user_cache(callback.from_user.id)

    completed_user = await complete_user_setup(session, callback.from_user.id)
    if completed_user is None:
        await callback.answer(i18n.get("settings-error-save"), show_alert=True)
        return

    await invalidate_user_cache(callback.from_user.id)

    from src.bot.handlers.commands import render_main_menu

    await render_main_menu(callback, completed_user, callback.from_user.full_name, i18n)
    await callback.answer(i18n.get("onboarding-preset-skipped"))
