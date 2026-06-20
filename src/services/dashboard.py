import asyncio
import logging
import time
from aiogram import Bot
from aiogram.types import LinkPreviewOptions
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from src.core.config import config
from src.database.session import async_session
from src.database.crud.channel_service import ChannelService
from src.bot.utils.dashboard_formatter import DashboardFormatter

logger = logging.getLogger(__name__)

DASHBOARD_CACHE_TTL_SEC = 55.0
_last_data: dict | None = None
_last_update_ts: float = 0.0

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
                try:
                    global _last_data, _last_update_ts
                    now_ts = time.time()

                    if (
                        _last_data is not None
                        and (now_ts - _last_update_ts) < DASHBOARD_CACHE_TTL_SEC
                    ):
                        combined_data = _last_data
                        logger.debug("Dashboard worker использует L2-кэш combined_data.")
                    else:
                        liq_data = liq_aggregator.get_top_liquidations(window_minutes=15)
                        market_data = market_aggregator.get_market_rankings(window_minutes=15)
                        combined_data = {**liq_data, **market_data}
                        _last_data = combined_data
                        _last_update_ts = now_ts
                        logger.debug("Dashboard worker собрал новые combined_data из агрегаторов.")

                    text = DashboardFormatter.compile_dashboard(combined_data, window_minutes=15)

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
                    logger.debug("Dashboard message успешно обновлен.")
                    
                except asyncio.TimeoutError:
                    logger.error("❌ Таймаут при редактировании дэшборда (10 сек).")
                    
                except TelegramForbiddenError:
                    logger.error(f"❌ Бот не имеет прав для редактирования сообщений в канале {config.PRIVATE_CHANNEL_ID}. Проверьте права администратора.")
                    
                except TelegramBadRequest as e:
                    error_msg = str(e).lower()
                    
                    # Self-healing: если сообщение не найдено или его нельзя редактировать
                    if "message to edit not found" in error_msg or "message can't be edited" in error_msg:
                        logger.error(f"❌ Сообщение дэшборда {message_id} потеряно или недоступно. Сбрасываю ID.")
                        async with async_session() as session:
                            await ChannelService.set_dashboard_id(session, None)
                    
                    # Игнорируем ошибку, если контент не изменился
                    elif "message is not modified" in error_msg:
                        logger.debug("Dashboard message не изменился.")
                    else:
                        logger.error(f"❌ Ошибка Telegram при обновлении дэшборда: {e}")
                
                except Exception as e:
                    logger.error(f"❌ Ошибка при сборке или отправке дэшборда: {e}", exc_info=True)
            
            # Ждем минуту перед следующим обновлением
            await asyncio.sleep(60)
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка в dashboard_worker: {e}", exc_info=True)
            await asyncio.sleep(10) # Короткая пауза перед перезапуском цикла при сбое
