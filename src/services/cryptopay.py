import logging
import os
from aiocryptopay import AioCryptoPay, Networks
from src.core.config import config

logger = logging.getLogger(__name__)

class CryptoPayService:
    def __init__(self):
        if config.PROXY_URL:
            os.environ['HTTP_PROXY'] = config.PROXY_URL
            os.environ['HTTPS_PROXY'] = config.PROXY_URL
            logger.info(f"Настроен системный прокси для CryptoPay: {config.PROXY_URL}")
        
        self.client = AioCryptoPay(
            token=config.CRYPTOPAY_TOKEN,
            network=Networks.TEST_NET if config.CRYPTOPAY_TESTNET else Networks.MAIN_NET
        )

    async def create_payment_invoice(self, amount: float, user_id: int) -> tuple[str, int] | None:
        """
        Создает инвойс в CryptoBot.
        
        :param amount: Сумма в USDT
        :param user_id: ID пользователя (для payload)
        :return: (pay_url, invoice_id) или None при ошибке
        """
        try:
            invoice = await self.client.create_invoice(
                asset='USDT',
                amount=amount,
                payload=str(user_id)
            )
            logger.info(f"Создан инвойс CryptoPay #{invoice.invoice_id} для пользователя {user_id} на сумму {amount}")
            return invoice.bot_invoice_url, invoice.invoice_id
        except Exception as e:
            logger.error(f"Ошибка при создании инвойса CryptoPay: {e}")
            return None

    async def check_invoice_status(self, invoice_id: int) -> str | None:
        """
        Проверяет статус инвойса.
        
        :param invoice_id: ID инвойса в системе CryptoPay
        :return: Статус ('active', 'paid', 'expired') или None при ошибке
        """
        try:
            invoices = await self.client.get_invoices(invoice_ids=invoice_id)
            if invoices and isinstance(invoices, list):
                return invoices[0].status
            elif hasattr(invoices, 'status'):
                return invoices.status
            return None
        except Exception as e:
            logger.error(f"Ошибка при проверке статуса инвойса {invoice_id}: {e}")
            return None

    async def close(self):
        """Закрывает сессию клиента."""
        await self.client.close()
        # Если мы создали кастомную aiohttp сессию, закрываем и её
        if hasattr(self.client, "_session") and hasattr(self.client._session, "close"):
            await self.client._session.close()

# Синглтон для использования в приложении
cryptopay = CryptoPayService()
