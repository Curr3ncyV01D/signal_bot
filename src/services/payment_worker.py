import asyncio
import logging
from aiogram import Bot
from src.database.session import async_session
from src.database.models import Invoice
from src.database.crud import billing_service
from src.services.cryptopay import cryptopay
from sqlalchemy import select

logger = logging.getLogger(__name__)

async def payment_checker_worker(bot: Bot):
    """
    Фоновый воркер для проверки статусов инвойсов CryptoPay.
    """
    logger.info("Запущен воркер проверки платежей CryptoPay")
    
    while True:
        try:
            async with async_session() as session:
                # 1. Получаем все PENDING инвойсы
                query = select(Invoice).where(Invoice.status == 'PENDING')
                result = await session.execute(query)
                pending_invoices = result.scalars().all()
                
                for inv in pending_invoices:
                    # 2. Проверяем статус в CryptoPay
                    status = await cryptopay.check_invoice_status(int(inv.crypto_pay_id))
                    
                    if status == 'paid':
                        # 3. Атомарно подтверждаем оплату (Баланс + Статус + Транзакция)
                        success = await billing_service.confirm_invoice_payment(session, inv.crypto_pay_id)
                        
                        if success:
                            # 4. Уведомляем пользователя
                            try:
                                await bot.send_message(
                                    chat_id=inv.user_id,
                                    text=f"✅ <b>Оплата получена!</b>\n\nВаш баланс пополнен на <b>{inv.amount} USDT</b>.",
                                    parse_mode="HTML"
                                )
                            except Exception as notify_err:
                                logger.error(f"Не удалось отправить уведомление пользователю {inv.user_id}: {notify_err}")
                                
                    elif status == 'expired':
                        # Обновляем статус на EXPIRED
                        await billing_service.update_invoice_status(session, inv.crypto_pay_id, 'EXPIRED')
                        logger.info(f"Инвойс #{inv.crypto_pay_id} истек")
                        
        except Exception as e:
            logger.error(f"Ошибка в payment_checker_worker: {e}")
            
        # Пауза 30 секунд
        await asyncio.sleep(30)
