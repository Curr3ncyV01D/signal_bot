import asyncio
import logging
from datetime import datetime, timezone

from aiogram import Bot
from sqlalchemy import select

from src.core.config import config
from src.database.crud import billing_service
from src.database.functions import get_utc_now
from src.database.models import Invoice, Transaction
from src.database.session import async_session
from src.services.analyzer import invalidate_user_cache
from src.services.cryptopay import cryptopay
from src.utils import format_datetime

logger = logging.getLogger(__name__)

ABANDONED_CART_REMINDER_MINUTES = 30
ABANDONED_CART_REMINDER_MAX_MINUTES = 120
INVOICE_EXPIRE_MINUTES = 24 * 60

class PaymentManager:
    """Контроль состояния воркера платежей (Heartbeat)"""
    last_run: datetime | None = None


async def _has_subscription_activation(
    session,
    user_id: int,
    crypto_pay_id: str
) -> bool:
    description = f"Direct Pay subscription via Invoice #{crypto_pay_id}"
    query = select(Transaction.id).where(
        Transaction.user_id == user_id,
        Transaction.type == "WITHDRAW",
        Transaction.description == description
    )
    result = await session.execute(query)
    return result.scalar_one_or_none() is not None


async def payment_checker_worker(bot: Bot):
    """Фоновый воркер для проверки статусов инвойсов CryptoPay."""
    logger.info("Запущен воркер проверки платежей CryptoPay")
    
    while True:
        PaymentManager.last_run = datetime.now(timezone.utc)
        try:
            async with async_session() as session:
                query = select(Invoice.id).where(Invoice.status == "PENDING")
                result = await session.execute(query)
                pending_invoice_ids = list(result.scalars().all())

                for invoice_id in pending_invoice_ids:
                    inv = await session.get(Invoice, invoice_id, with_for_update=True)
                    if not inv or inv.status != "PENDING":
                        continue

                    now = get_utc_now()
                    age_minutes = (now - inv.created_at).total_seconds() / 60

                    if age_minutes >= INVOICE_EXPIRE_MINUTES:
                        inv.status = "EXPIRED"
                        await session.commit()
                        logger.info(f"Инвойс #{inv.crypto_pay_id} закрыт по таймауту (24ч)")
                        continue

                    if (
                        age_minutes >= ABANDONED_CART_REMINDER_MINUTES
                        and age_minutes <= ABANDONED_CART_REMINDER_MAX_MINUTES
                        and not inv.is_reminder_sent
                    ):
                        try:
                            await bot.send_message(
                                chat_id=inv.user_id,
                                text="⏳ <b>Ваша ссылка на оплату всё еще активна.</b>\n\n"
                                     "Если возникли трудности с оплатой — напишите в поддержку.",
                                parse_mode="HTML"
                            )
                            inv.is_reminder_sent = True
                            await session.commit()
                            logger.info(f"Отправлено напоминание о брошенной корзине пользователю {inv.user_id}")
                        except Exception as e:
                            logger.warning(f"Не удалось отправить напоминание {inv.user_id}: {e}")

                    status = await cryptopay.check_invoice_status(int(inv.crypto_pay_id))

                    if status == "paid":
                        success = await billing_service.confirm_invoice_payment(session, inv.crypto_pay_id)

                        if not success:
                            await session.rollback()
                            continue

                        activated_sub = False
                        new_end: datetime | None = None

                        if inv.payload and inv.payload.startswith("sub_"):
                            try:
                                already_activated = await _has_subscription_activation(
                                    session=session,
                                    user_id=inv.user_id,
                                    crypto_pay_id=inv.crypto_pay_id
                                )
                                if not already_activated:
                                    days = int(inv.payload.split("_", 1)[1])
                                    price = round(float(config.TARIFFS.get(days, inv.amount)), 2)
                                    success_charge, new_end, _ = await billing_service.charge_and_activate_subscription(
                                        session=session,
                                        user_id=inv.user_id,
                                        days=days,
                                        price=price,
                                        description=f"Direct Pay subscription via Invoice #{inv.crypto_pay_id}"
                                    )
                                    if success_charge:
                                        activated_sub = True
                                        logger.info(
                                            f"Авто-активация подписки для {inv.user_id} "
                                            f"по инвойсу #{inv.crypto_pay_id} успешна"
                                        )
                                    else:
                                        logger.warning(
                                            f"Не удалось активировать подписку для {inv.user_id} "
                                            f"по инвойсу #{inv.crypto_pay_id}"
                                        )
                            except Exception as sub_err:
                                await session.rollback()
                                logger.error(f"Ошибка авто-активации для {inv.user_id}: {sub_err}")
                                continue

                        await session.commit()

                        if activated_sub:
                            await invalidate_user_cache()

                        try:
                            if activated_sub and new_end:
                                await bot.send_message(
                                    chat_id=inv.user_id,
                                    text=(
                                    "✅ <b>Оплата подтверждена!</b>\n\n"
                                    f"Ваша подписка активирована до <b>{format_datetime(new_end)}</b>."
                                    ),
                                    parse_mode="HTML"
                                )
                            else:
                                await bot.send_message(
                                    chat_id=inv.user_id,
                                    text=(
                                        "✅ <b>Оплата получена!</b>\n\n"
                                        f"Ваш баланс пополнен на <b>{inv.amount} USDT</b>."
                                    ),
                                    parse_mode="HTML"
                                )
                        except Exception as notify_err:
                            logger.error(f"Не удалось отправить уведомление пользователю {inv.user_id}: {notify_err}")

                    elif status in ["expired", "deleted", "cancelled"]:
                        inv.status = "EXPIRED"
                        await session.commit()
                        logger.info(f"Инвойс #{inv.crypto_pay_id} закрыт (статус: {status})")

        except Exception as e:
            logger.error(f"Ошибка в payment_checker_worker: {e}")

        await asyncio.sleep(30)
