import asyncio
import logging
from datetime import datetime, timedelta, timezone

from aiogram import Bot
from sqlalchemy import select

from src.core.i18n_runtime import background_i18n
from src.core.localization import normalize_locale_code
from src.database.functions import get_utc_now
from src.database.models import Invoice, User
from src.database.session import async_session
from src.services.logic.billing_processor import process_payment_update
from src.utils import format_datetime, format_smart_num

logger = logging.getLogger(__name__)

ABANDONED_CART_REMINDER_MINUTES = 30
ABANDONED_CART_REMINDER_MAX_MINUTES = 120
INVOICE_EXPIRE_MINUTES = 120
FAST_POLL_UNTIL_MINUTES = 15
FAST_POLL_INTERVAL_SECONDS = 30
SLOW_POLL_INTERVAL_SECONDS = 180
POLLING_CONCURRENCY = 5

class PaymentManager:
    """Контроль состояния воркера платежей (Heartbeat)"""
    last_run: datetime | None = None
    next_poll_at: dict[str, datetime] = {}


def _get_i18n_text(locale: str | None, key: str, **kwargs: object) -> str:
    return background_i18n.get(
        key,
        locale=normalize_locale_code(locale),
        **kwargs,
    )


def _resolve_poll_interval_seconds(age_minutes: float) -> int:
    return FAST_POLL_INTERVAL_SECONDS if age_minutes < FAST_POLL_UNTIL_MINUTES else SLOW_POLL_INTERVAL_SECONDS


async def _process_invoice(bot: Bot, invoice_id: int, semaphore: asyncio.Semaphore) -> None:
    async with semaphore:
        async with async_session() as session:
            inv = await session.get(Invoice, invoice_id)
            if not inv or inv.status not in {"PENDING", "PARTIAL"}:
                if inv:
                    PaymentManager.next_poll_at.pop(inv.external_id, None)
                return

            invoice_external_id = str(inv.external_id)
            invoice_user_id = int(inv.user_id)
            invoice_created_at = inv.created_at
            invoice_reminder_sent = bool(inv.is_reminder_sent)
            user = await session.get(User, invoice_user_id)
            user_locale = normalize_locale_code(user.language_code if user else None)

            now = get_utc_now()
            age_minutes = (now - invoice_created_at).total_seconds() / 60

            if age_minutes >= INVOICE_EXPIRE_MINUTES:
                inv.status = "EXPIRED"
                await session.commit()
                PaymentManager.next_poll_at.pop(invoice_external_id, None)
                logger.info("Инвойс #%s закрыт по таймауту (%s мин)", invoice_external_id, INVOICE_EXPIRE_MINUTES)
                return

            PaymentManager.next_poll_at[invoice_external_id] = now + timedelta(seconds=_resolve_poll_interval_seconds(age_minutes))

            if (
                age_minutes >= ABANDONED_CART_REMINDER_MINUTES
                and age_minutes <= ABANDONED_CART_REMINDER_MAX_MINUTES
                and not invoice_reminder_sent
            ):
                try:
                    await bot.send_message(
                        chat_id=invoice_user_id,
                        text=_get_i18n_text(user_locale, "payment-worker-reminder-active-link"),
                        parse_mode="HTML"
                    )
                    inv.is_reminder_sent = True
                    await session.commit()
                    logger.info("Отправлено напоминание о брошенной корзине пользователю %s", invoice_user_id)
                except Exception as e:
                    logger.warning("Не удалось отправить напоминание %s: %s", invoice_user_id, e)

            payment_result = await process_payment_update(session, invoice_external_id)

            if payment_result.sub_activated and payment_result.new_end_date:
                PaymentManager.next_poll_at.pop(invoice_external_id, None)
                try:
                    await bot.send_message(
                        chat_id=invoice_user_id,
                        text=_get_i18n_text(
                            user_locale,
                            "payment-worker-subscription-paid-notification",
                            amount=f"{format_smart_num(payment_result.delta_credited or payment_result.amount_actual)} USDT",
                            days=payment_result.intent_days or 0,
                            new_end=format_datetime(payment_result.new_end_date),
                        ),
                        parse_mode="HTML"
                    )
                except Exception as notify_err:
                    logger.error("Не удалось отправить уведомление пользователю %s: %s", invoice_user_id, notify_err)

            elif payment_result.intent_action == "sub" and payment_result.is_paid and not payment_result.sub_activated:
                try:
                    await bot.send_message(
                        chat_id=invoice_user_id,
                        text=_get_i18n_text(
                            user_locale,
                            "payment-worker-price-changed-notification",
                            balance=f"{format_smart_num(payment_result.new_balance)} USDT",
                            needed=f"{format_smart_num(payment_result.needed_amount)} USDT",
                        ),
                        parse_mode="HTML",
                    )
                except Exception as notify_err:
                    logger.error("Не удалось отправить уведомление о неавтоактивированной подписке пользователю %s: %s", invoice_user_id, notify_err)

            elif payment_result.delta_credited > 0:
                try:
                    await bot.send_message(
                        chat_id=invoice_user_id,
                        text=_get_i18n_text(
                            user_locale,
                            "payment-worker-balance-paid-notification",
                            amount=f"{format_smart_num(payment_result.delta_credited)} USDT",
                        ),
                        parse_mode="HTML"
                    )
                except Exception as notify_err:
                    logger.error("Не удалось отправить уведомление о пополнении пользователю %s: %s", invoice_user_id, notify_err)

                if not payment_result.is_paid and payment_result.amount_actual > 0:
                    try:
                        await bot.send_message(
                            chat_id=invoice_user_id,
                            text=_get_i18n_text(
                                user_locale,
                                "payment-worker-partial-payment-notification",
                                paid_amount=f"{format_smart_num(payment_result.amount_actual)} USDT",
                                expected_amount=f"{format_smart_num(payment_result.amount_expected)} USDT",
                                needed_amount=f"{format_smart_num(payment_result.needed_amount)} USDT",
                            ),
                            parse_mode="HTML"
                        )
                    except Exception as notify_err:
                        logger.error("Не удалось отправить уведомление о частичной оплате пользователю %s: %s", invoice_user_id, notify_err)

            elif payment_result.invoice_status in {"EXPIRED", "PAID"}:
                PaymentManager.next_poll_at.pop(invoice_external_id, None)


async def payment_checker_worker(bot: Bot):
    """Фоновый воркер для проверки статусов инвойсов."""
    logger.info("Запущен воркер проверки платежей")
    semaphore = asyncio.Semaphore(POLLING_CONCURRENCY)

    while True:
        PaymentManager.last_run = datetime.now(timezone.utc)
        try:
            async with async_session() as session:
                query = select(Invoice.id, Invoice.external_id).where(Invoice.status.in_(("PENDING", "PARTIAL")))
                result = await session.execute(query)
                pending_invoices = list(result.all())

            now = get_utc_now()
            invoice_ids_to_poll = [
                invoice_id
                for invoice_id, external_id in pending_invoices
                if PaymentManager.next_poll_at.get(external_id, now) <= now
            ]

            if invoice_ids_to_poll:
                await asyncio.gather(*(_process_invoice(bot, invoice_id, semaphore) for invoice_id in invoice_ids_to_poll))

        except Exception as e:
            logger.error(f"Ошибка в payment_checker_worker: {e}")

        await asyncio.sleep(30)
