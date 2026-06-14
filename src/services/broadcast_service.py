import asyncio
import logging
import time
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.utils.markdown import hbold
from src.bot.notifier import broadcaster_semaphore

logger = logging.getLogger(__name__)

async def run_broadcast(
    bot: Bot, 
    user_ids: list[int], 
    from_chat_id: int, 
    message_id: int,
    admin_id: int | None = None
) -> dict:
    """
    Асинхронная рассылка сообщения по списку ID пользователей.
    Использует метод copy_message для сохранения контента и кнопок.
    
    :param bot: Экземпляр бота
    :param user_ids: Список Telegram ID получателей
    :param from_chat_id: ID чата-источника (откуда копируем)
    :param message_id: ID сообщения в источнике
    :param admin_id: ID админа для отправки отчета (опционально)
    :return: Словарь с результатами рассылки
    """
    start_time = time.time()
    total = len(user_ids)
    success = 0
    blocked = 0
    errors = 0
    
    logger.info(f"📣 Запуск рассылки на {total} пользователей.")
    
    for user_id in user_ids:
        async with broadcaster_semaphore:
            try:
                await bot.copy_message(
                    chat_id=user_id,
                    from_chat_id=from_chat_id,
                    message_id=message_id
                )
                success += 1
            except TelegramForbiddenError:
                blocked += 1
            except TelegramRetryAfter as e:
                logger.warning(f"⏳ Flood limit достигнут. Ожидание {e.retry_after} сек.")
                await asyncio.sleep(e.retry_after)
                # Повторная попытка после ожидания
                try:
                    await bot.copy_message(
                        chat_id=user_id,
                        from_chat_id=from_chat_id,
                        message_id=message_id
                    )
                    success += 1
                except TelegramForbiddenError:
                    blocked += 1
                except Exception as ex:
                    logger.error(f"❌ Ошибка при повторной отправке пользователю {user_id}: {ex}")
                    errors += 1
            except Exception as e:
                logger.error(f"❌ Непредвиденная ошибка при отправке пользователю {user_id}: {e}")
                errors += 1
            
            await asyncio.sleep(0.05)
            
    duration = int(time.time() - start_time)
    logger.info(f"🏁 Рассылка завершена. Успешно: {success}, Блокировок: {blocked}, Ошибок: {errors}")
    
    results = {
        "total": total,
        "success": success,
        "blocked": blocked,
        "errors": errors,
        "duration": duration
    }

    if admin_id:
        report = (
            f"🏁 {hbold('Рассылка завершена!')}\n\n"
            f"👥 {hbold('Всего в сегменте:')} {total}\n"
            f"✅ {hbold('Успешно доставлено:')} {success}\n"
            f"🚫 {hbold('Заблокировали бота:')} {blocked}\n"
            f"❌ {hbold('Технические ошибки:')} {errors}\n"
            f"⏱ {hbold('Затрачено времени:')} {duration} сек."
        )
        try:
            await bot.send_message(admin_id, report, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Не удалось отправить отчет админу {admin_id}: {e}")

    return results
