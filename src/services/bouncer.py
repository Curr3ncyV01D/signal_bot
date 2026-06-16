import asyncio
import logging
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from datetime import datetime, timezone

from src.core.config import config
from src.database.session import async_session
from src.database.crud.user_service import get_expired_users, clear_expired_subscription

logger = logging.getLogger(__name__)

class BouncerManager:
    last_run: datetime | None = None

async def bouncer_worker(bot: Bot, interval_minutes: int = 15):
    """
    Фоновая задача "Вышибала".
    Ищет юзеров с истекшей подпиской, кикает из канала и обнуляет дату в БД.
    """
    logger.info(f"👮‍♂️ Вышибала (Bouncer) запущен. Проверка каждые {interval_minutes} минут.")
    
    while True:
        try:
            BouncerManager.last_run = datetime.now(timezone.utc)
            async with async_session() as session:
                expired_users = await get_expired_users(session)
                
                if expired_users:
                    logger.info(f"👮‍♂️ Вышибала нашел {len(expired_users)} пользователей с истекшей подпиской/триалом.")
                
                for user in expired_users:
                    try:
                        # 1. Удаляем из закрытого канала (бан + сразу анбан, чтобы мог вернуться в будущем)
                        await bot.ban_chat_member(
                            chat_id=config.PRIVATE_CHANNEL_ID,
                            user_id=user.id
                        )
                        await bot.unban_chat_member(
                            chat_id=config.PRIVATE_CHANNEL_ID,
                            user_id=user.id
                        )
                        logger.info(f"Пользователь {user.id} исключен из канала.")
                        
                        # 2. Отправляем уведомление в ЛС
                        try:
                            text = (
                                "⚠️ <b>Срок действия вашей подписки/триала истек.</b>\n\n"
                                "Вы были исключены из VIP-канала, а рассылка сигналов приостановлена.\n"
                                "Нажмите /start для обновления доступа."
                            )
                            await bot.send_message(user.id, text, parse_mode="HTML")
                        except TelegramForbiddenError:
                            logger.warning(f"Не удалось отправить прощальное сообщение {user.id} (этот пользователь недоступен бота).")
                        
                        # 3. Обнуляем дату в БД, чтобы Вышибала больше его не трогал
                        await clear_expired_subscription(session, user.id)
                        
                    except TelegramBadRequest as e:
                        # Если юзер уже сам вышел из канала или бот не админ
                        logger.warning(f"Ошибка при исключении {user.id} (возможно, уже покинул канал сам): {e}")
                        # Все равно обнуляем подписку, чтобы не долбить API Telegram
                        await clear_expired_subscription(session, user.id)
                    except Exception as e:
                        logger.error(f"Неизвестная ошибка при обработке {user.id}: {e}")
                    
                    # Защита от лимитов Telegram API (FloodWait) при массовом исключении
                    await asyncio.sleep(0.5)

        except asyncio.CancelledError:
            logger.info("👮‍♂️ Вышибала остановлен.")
            break
        except Exception as e:
            logger.error(f"Ошибка в основном цикле Вышибалы: {e}")
        
        # Ждем до следующей проверки (переводим минуты в секунды)
        await asyncio.sleep(interval_minutes * 60)