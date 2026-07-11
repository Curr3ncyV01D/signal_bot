import asyncio
import logging
from datetime import datetime, timedelta, timezone

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import config
from src.database.crud import billing_service
from src.database.functions import get_utc_now
from src.database.models import Transaction, User
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

async def _safe_send_message(bot: Bot, user_id: int, text: str) -> bool:
    try:
        await bot.send_message(user_id, text, parse_mode="HTML")
        return True
    except TelegramForbiddenError:
        logger.warning(f"Не удалось отправить сообщение {user_id}: пользователь недоступен боту.")
        return False
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения пользователю {user_id}: {e}")
        return False


async def _has_active_trial_access(session: AsyncSession, user: User) -> bool:
    if not user.subscription_end or not user.is_trial_used:
        return False

    result = await session.execute(
        select(Transaction)
        .where(
            Transaction.user_id == user.id,
            Transaction.type == "WITHDRAW",
            Transaction.amount == 0,
            Transaction.description == f"Trial {config.TRIAL_DURATION_DAYS}d",
        )
        .order_by(Transaction.created_at.desc())
        .limit(1)
    )
    trial_tx = result.scalar_one_or_none()
    if trial_tx is None:
        return False

    expected_trial_end = trial_tx.created_at + timedelta(days=config.TRIAL_DURATION_DAYS)
    return abs((user.subscription_end - expected_trial_end).total_seconds()) <= 300

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
    is_active_trial = await _has_active_trial_access(session, user)
    if is_active_trial:
        in_warning_window = TRIAL_EXPIRY_WARNING_MIN_MINUTES <= minutes_left <= TRIAL_EXPIRY_WARNING_MAX_MINUTES
        warning_threshold = user.subscription_end - timedelta(minutes=TRIAL_EXPIRY_WARNING_MAX_MINUTES)
        warning_text = (
            "⏳ <b>Ваш пробный доступ истекает через 1 час.</b>\n\n"
            "Чтобы не потерять доступ к сигналам, продлите подписку заранее в меню /start."
        )
    else:
        in_warning_window = EXPIRY_WARNING_24H_MIN_HOURS <= hours_left <= EXPIRY_WARNING_24H_MAX_HOURS
        warning_threshold = user.subscription_end - timedelta(hours=EXPIRY_WARNING_24H_MAX_HOURS)
        warning_text = (
            "⏳ <b>Ваша подписка истекает через 24 часа.</b>\n\n"
            "Убедитесь, что на балансе достаточно средств для автопродления, "
            "или продлите её вручную в меню /start."
        )

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
        await invalidate_user_cache()
        await _safe_send_message(
            bot,
            user.id,
            (
                "✅ <b>Подписка продлена!</b>\n\n"
                f"Мы успешно списали {monthly_price:.2f} USDT с вашего баланса. "
                "Спасибо, что остаетесь с нами."
            )
        )
        return True

    should_notify = (
        user.last_renewal_attempt is None
        or (now - user.last_renewal_attempt) >= timedelta(hours=AUTO_RENEWAL_COOLDOWN_HOURS)
    )
    if should_notify:
        sent = await _safe_send_message(
            bot,
            user.id,
            (
                "⚠️ <b>Недостаточно средств!</b>\n\n"
                "Мы не смогли продлить подписку автоматически. Пополните баланс, "
                "чтобы не потерять доступ к персональным сигналам через 1 час."
            )
        )
        if sent:
            user.last_renewal_attempt = now
            await session.commit()

    return False

async def _handle_subscription_expiry(session: AsyncSession, bot: Bot, user: User) -> None:
    await _safe_send_message(
        bot,
        user.id,
        (
            "⚠️ <b>Срок действия вашей подписки/триала истек.</b>\n\n"
            "Персональная рассылка сигналов приостановлена.\n"
            "Нажмите /start и продлите подписку, чтобы восстановить доступ."
        )
    )

    user.subscription_end = None
    user.last_expiry_warning_at = None
    await session.commit()
    await invalidate_user_cache(user.id)

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
