import asyncio
import logging
from aiogram import Bot
from aiogram.types import LinkPreviewOptions
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from src.core.config import config
from src.database.session import async_session
from src.database.crud.channel_service import ChannelService
from src.bot.utils.dashboard_formatter import DashboardFormatter

logger = logging.getLogger(__name__)

async def dashboard_worker(bot: Bot, liq_aggregator, market_aggregator):
    """
    Фоновый воркер для автоматического обновления закрепленного дэшборда в VIP-канале.
    """
    logger.info("🚀 Dashboard worker запущен.")
    
    while True:
        try:
            # 1. Получаем текущие настройки (из кэша)
            settings = ChannelService.get_cached_settings()
            message_id = settings.dashboard_message_id
            
            if message_id:
                # 2. Собираем данные из агрегаторов (окно 15 минут)
                try:
                    liq_data = liq_aggregator.get_top_liquidations(window_minutes=15)
                    market_data = market_aggregator.get_market_rankings(window_minutes=15)
                    
                    # Объединяем данные для форматтера
                    combined_data = {**liq_data, **market_data}
                    
                    # 3. Форматируем текст
                    text = DashboardFormatter.compile_dashboard(combined_data, window_minutes=15)
                    
                    # 4. Редактируем сообщение
                    await asyncio.wait_for(
                        bot.edit_message_text(
                            chat_id=config.PRIVATE_CHANNEL_ID,
                            message_id=message_id,
                            text=text,
                            parse_mode="HTML",
                            link_preview_options=LinkPreviewOptions(is_disabled=True)
                        ),
                        timeout=10.0
                    )
                    
                except asyncio.TimeoutError:
                    logger.warning("⚠️ Таймаут при редактировании дэшборда (10 сек).")
                    
                except TelegramForbiddenError:
                    logger.error(f"❌ Бот не имеет прав для редактирования сообщений в канале {config.PRIVATE_CHANNEL_ID}. Проверьте права администратора.")
                    
                except TelegramBadRequest as e:
                    error_msg = str(e).lower()
                    
                    # Self-healing: если сообщение не найдено или его нельзя редактировать
                    if "message to edit not found" in error_msg or "message can't be edited" in error_msg:
                        logger.warning(f"⚠️ Сообщение дэшборда {message_id} потеряно или недоступно. Сбрасываю ID.")
                        async with async_session() as session:
                            await ChannelService.set_dashboard_id(session, None)
                    
                    # Игнорируем ошибку, если контент не изменился
                    elif "message is not modified" in error_msg:
                        pass
                    else:
                        logger.error(f"❌ Ошибка Telegram при обновлении дэшборда: {e}")
                
                except Exception as e:
                    logger.error(f"❌ Ошибка при сборке или отправке дэшборда: {e}", exc_info=True)
            
            # Ждем минуту перед следующим обновлением
            await asyncio.sleep(60)
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка в dashboard_worker: {e}", exc_info=True)
            await asyncio.sleep(10) # Короткая пауза перед перезапуском цикла при сбое
