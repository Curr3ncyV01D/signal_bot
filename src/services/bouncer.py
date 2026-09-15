import asyncio
import logging
from datetime import datetime, timedelta, timezone

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import config
from src.core.i18n_runtime import background_i18n
from src.core.localization import normalize_locale_code
from src.core.redis_bus import redis_bus
from src.database.crud import billing_service
from src.database.crud.user_service import degrade_user_to_free_tier
from src.database.functions import get_utc_now
from src.database.models import User
from src.database.session import async_session
from src.services.analyzer import invalidate_user_cache

logger = logging.getLogger(__name__)

AUTO_RENEWAL_DAYS = 30
AUTO_RENEWAL_WINDOW_MINUTES = 60
AUTO_RENEWAL_COOLDOWN_HOURS = 24
EXPIRY_WARNING_24H_MIN_HOURS = 23
EXPIRY_WARNING_24H_MAX_HOURS = 25
TRIAL_EXPIRY_WARNING_MIN_MINUTES = 45
TRIAL_EXPIRY_WARNING_MAX_MINUTES = 75

class BouncerManager:
    last_run: datetime | None = None

async def _safe_send_message(
    bot: Bot,
    user_id: int,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> bool:
    try:
        await bot.send_message(user_id, text, parse_mode="HTML", reply_markup=reply_markup)
        return True
    except TelegramForbiddenError:
        logger.warning(f"Не удалось отправить сообщение {user_id}: пользователь недоступен боту.")
        return False
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения пользователю {user_id}: {e}")
        return False


async def _handle_expiry_warning(
    session: AsyncSession,
    bot: Bot,
    user: User,
    now: datetime
) -> None:
    if not user.subscription_end:
        return

    hours_left = (user.subscription_end - now).total_seconds() / 3600
    minutes_left = (user.subscription_end - now).total_seconds() / 60
    is_active_trial = await billing_service.has_active_trial_bonus(session, user)
    user_locale = normalize_locale_code(user.language_code)
    if is_active_trial:
        in_warning_window = TRIAL_EXPIRY_WARNING_MIN_MINUTES <= minutes_left <= TRIAL_EXPIRY_WARNING_MAX_MINUTES
        warning_threshold = user.subscription_end - timedelta(minutes=TRIAL_EXPIRY_WARNING_MAX_MINUTES)
        warning_text = background_i18n.get("bouncer-trial-expiry-warning", locale=user_locale)
    else:
        in_warning_window = EXPIRY_WARNING_24H_MIN_HOURS <= hours_left <= EXPIRY_WARNING_24H_MAX_HOURS
        warning_threshold = user.subscription_end - timedelta(hours=EXPIRY_WARNING_24H_MAX_HOURS)
        warning_text = background_i18n.get("bouncer-subscription-expiry-warning", locale=user_locale)

    if not in_warning_window:
        return

    if user.last_expiry_warning_at and user.last_expiry_warning_at >= warning_threshold:
        return

    sent = await _safe_send_message(bot, user.id, warning_text)
    if sent:
        user.last_expiry_warning_at = now
        await session.commit()

async def _handle_auto_renewal(
    session: AsyncSession,
    bot: Bot,
    user: User,
    now: datetime
) -> bool:
    if not user.subscription_end:
        return False

    minutes_left = (user.subscription_end - now).total_seconds() / 60
    in_renew_window = 0 <= minutes_left <= AUTO_RENEWAL_WINDOW_MINUTES
    if not in_renew_window or not user.auto_renewal:
        return False

    monthly_price = round(float(config.SUB_MONTHLY_PRICE), 2)
    if round(float(user.balance), 2) >= monthly_price:
        success, new_end, _ = await billing_service.charge_and_activate_subscription(
            session=session,
            user_id=user.id,
            days=AUTO_RENEWAL_DAYS,
            price=monthly_price,
            description="Автопродление подписки на 30 дн."
        )
        if not success or not new_end:
            return False

        user.last_renewal_attempt = None
        user.last_expiry_warning_at = None
        await session.commit()
        await invalidate_user_cache(user.id)
        
        user_locale = normalize_locale_code(user.language_code)
        await _safe_send_message(
            bot,
            user.id,
            background_i18n.get(
                "bouncer-auto-renewal-success", 
                locale=user_locale, 
                amount=f"{monthly_price:.2f}"
            )
        )
        return True

    should_notify = (
        user.last_renewal_attempt is None
        or (now - user.last_renewal_attempt) >= timedelta(hours=AUTO_RENEWAL_COOLDOWN_HOURS)
    )
    if should_notify:
        user_locale = normalize_locale_code(user.language_code)
        sent = await _safe_send_message(
            bot,
            user.id,
            background_i18n.get("bouncer-auto-renewal-failed-balance", locale=user_locale)
        )
        if sent:
            user.last_renewal_attempt = now
            await session.commit()

    return False

_ALLOWED_MEMBER_STATUSES = {"member", "administrator", "creator", "restricted"}


async def _check_media_resources_membership(bot: Bot, user_id: int) -> bool:
    """
    Проверяет членство пользователя в Новостном канале и Чате сообщества.
    Оба ресурса требуются одновременно (AND).
    Если какой-то ID ресурса не задан в конфиге — считаем его выполненным.
    При любой ошибке доступа — возвращаем False (fail-closed, conservative).
    """
    if not config.NEWS_CHANNEL_ID and not config.COMMUNITY_GROUP_ID:
        return True

    checks: list[tuple[int | str | None, str]] = [
        (config.NEWS_CHANNEL_ID, "NEWS_CHANNEL_ID"),
        (config.COMMUNITY_GROUP_ID, "COMMUNITY_GROUP_ID"),
    ]

    for resource_id, _name in checks:
        if resource_id is None:
            continue
        if isinstance(resource_id, str) and not resource_id.strip():
            continue
        try:
            member = await bot.get_chat_member(resource_id, user_id)
            status = getattr(member, "status", None)
            if status not in _ALLOWED_MEMBER_STATUSES:
                return False
        except TelegramBadRequest:
            logger.warning(
                "_check_media_resources_membership: TelegramBadRequest для user_id=%s, resource=%s",
                user_id, _name,
            )
            return False
        except TelegramForbiddenError:
            logger.warning(
                "_check_media_resources_membership: TelegramForbiddenError для user_id=%s, resource=%s",
                user_id, _name,
            )
            return False
        except Exception as e:
            logger.error(
                "_check_media_resources_membership: unhandled error для user_id=%s, resource=%s: %s",
                user_id, _name, e,
            )
            return False

    return True


def _build_gate_verify_keyboard(user_locale: str) -> InlineKeyboardMarkup | None:
    """
    Собирает inline-клавиатуру Gatekeeper: ссылки на ресурсы + кнопка проверки.
    Если ссылки на ресурсы не заданы — возвращает None (отправка без клавиатуры).
    """
    buttons: list[InlineKeyboardButton] = []

    news_channel_url = (config.NEWS_CHANNEL_URL or "").strip()
    if news_channel_url:
        buttons.append(
            InlineKeyboardButton(
                text=background_i18n.get("gate-button-channel", locale=user_locale),
                url=news_channel_url,
            )
        )

    community_group_link = (config.COMMUNITY_GROUP_LINK or "").strip()
    if community_group_link:
        buttons.append(
            InlineKeyboardButton(
                text=background_i18n.get("gate-button-chat", locale=user_locale),
                url=community_group_link,
            )
        )

    if not buttons:
        return None

    builder_buttons: list[list[InlineKeyboardButton]] = [[b] for b in buttons]
    builder_buttons.append(
        [
            InlineKeyboardButton(
                text=background_i18n.get("gate-button-verify", locale=user_locale),
                callback_data="verify_community_join",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=builder_buttons)


async def _handle_subscription_expiry(session: AsyncSession, bot: Bot, user: User) -> None:
    user_locale = normalize_locale_code(user.language_code)

    updated_user = await degrade_user_to_free_tier(session, user.id)
    if updated_user is None:
        logger.warning(f"degrade_user_to_free_tier вернул None для пользователя {user.id}")
        return

    target_user_id = updated_user.id
    await invalidate_user_cache(target_user_id)

    is_member = await _check_media_resources_membership(bot, target_user_id)
    await redis_bus.set_gate_status(target_user_id, is_member, ttl=config.GATE_CACHE_TTL_SEC)

    if is_member:
        text = background_i18n.get("bouncer-degraded-to-free-notification", locale=user_locale)
        await _safe_send_message(bot, target_user_id, text)
    else:
        text = background_i18n.get("bouncer-expired-unsubscribed-notification", locale=user_locale)
        keyboard = _build_gate_verify_keyboard(user_locale)
        await _safe_send_message(bot, target_user_id, text, reply_markup=keyboard)

async def bouncer_worker(bot: Bot, interval_minutes: int = 15):
    """
    Фоновая задача "Вышибала".
    Проверяет автопродление, уведомляет о нехватке средств и
    отключает персональную рассылку после истечения подписки.
    """
    logger.info(f"👮‍♂️ Вышибала (Bouncer) запущен. Проверка каждые {interval_minutes} минут.")

    while True:
        try:
            BouncerManager.last_run = datetime.now(timezone.utc)
            async with async_session() as session:
                now = get_utc_now()
                query = select(User.id).where(
                    User.subscription_end.is_not(None),
                    User.subscription_end <= now + timedelta(hours=EXPIRY_WARNING_24H_MAX_HOURS)
                )
                result = await session.execute(query)
                candidate_ids = list(result.scalars().all())

                if candidate_ids:
                    logger.debug(
                        f"👮‍♂️ Вышибала нашел {len(candidate_ids)} пользователей "
                        "в окне автопродления/истечения."
                    )

                for user_id in candidate_ids:
                    user = await session.get(User, user_id, with_for_update=True)
                    if not user or not user.subscription_end:
                        continue

                    now = get_utc_now()
                    try:
                        await _handle_expiry_warning(session, bot, user, now)
                        renewed = await _handle_auto_renewal(session, bot, user, now)
                        if renewed:
                            continue

                        if user.subscription_end <= now:
                            await _handle_subscription_expiry(session, bot, user)
                    except Exception as e:
                        await session.rollback()
                        logger.error(f"Неизвестная ошибка при обработке {user.id}: {e}")

                    await asyncio.sleep(0.5)

        except asyncio.CancelledError:
            logger.info("👮‍♂️ Вышибала остановлен.")
            break
        except Exception as e:
            logger.error(f"Ошибка в основном цикле Вышибалы: {e}")

        await asyncio.sleep(interval_minutes * 60)
