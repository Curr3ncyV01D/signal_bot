import asyncio
import logging
import time
from datetime import datetime, timezone
from aiogram import Bot
from aiogram.types import LinkPreviewOptions
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from src.core.config import config
from src.database.session import async_session
from src.bot.utils.dashboard_formatter import DashboardFormatter
from src.services.rendering.asset_manager import AssetManager

logger = logging.getLogger(__name__)

DASHBOARD_CACHE_TTL_SEC = 55.0
DASHBOARD_MESSAGE_ID_KEY = "dashboard_message_id"
LAST_SUMMARY_AT_KEY = "last_summary_at"
_last_data: dict | None = None
_last_update_ts: float = 0.0
_dashboard_recreate_in_progress = False
_cached_dashboard_message_id: int | None = None


def _get_combined_data(liq_aggregator, market_aggregator, use_cache: bool = True) -> dict:
    global _last_data, _last_update_ts

    now_ts = time.time()
    if use_cache and _last_data is not None and (now_ts - _last_update_ts) < DASHBOARD_CACHE_TTL_SEC:
        logger.debug("Dashboard worker использует L2-кэш combined_data.")
        return _last_data

    liq_data = liq_aggregator.get_top_liquidations(window_minutes=15)
    market_data = market_aggregator.get_market_rankings(window_minutes=15)
    combined_data = {**liq_data, **market_data}
    _last_data = combined_data
    _last_update_ts = now_ts
    return combined_data


async def _get_dashboard_message_id() -> int | None:
    global _cached_dashboard_message_id

    if _cached_dashboard_message_id is not None:
        return _cached_dashboard_message_id

    async with async_session() as session:
        raw_value = await AssetManager.get_metadata_value(session, DASHBOARD_MESSAGE_ID_KEY)

    if raw_value is None or raw_value == "":
        return None

    try:
        _cached_dashboard_message_id = int(raw_value)
    except (TypeError, ValueError):
        logger.warning("Некорректный `%s` в system_metadata: %s", DASHBOARD_MESSAGE_ID_KEY, raw_value)
        _cached_dashboard_message_id = None

    return _cached_dashboard_message_id


async def _set_dashboard_message_id(message_id: int | None) -> None:
    global _cached_dashboard_message_id

    async with async_session() as session:
        if message_id is None:
            await AssetManager.upsert_metadata_value(session, DASHBOARD_MESSAGE_ID_KEY, "")
        else:
            await AssetManager.upsert_metadata_value(session, DASHBOARD_MESSAGE_ID_KEY, str(message_id))
        await session.commit()

    _cached_dashboard_message_id = message_id


async def _set_last_summary_at() -> None:
    async with async_session() as session:
        await AssetManager.upsert_metadata_value(
            session,
            LAST_SUMMARY_AT_KEY,
            datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        )
        await session.commit()


async def recreate_dashboard_logic(bot: Bot, liq_aggregator, market_aggregator) -> int | None:
    """Пересоздает дэшборд в канале и сохраняет новый `dashboard_message_id`."""
    global _dashboard_recreate_in_progress, _last_data, _last_update_ts

    if _dashboard_recreate_in_progress:
        logger.debug("Пропуск пересоздания дэшборда: операция уже выполняется.")
        return None

    _dashboard_recreate_in_progress = True
    try:
        old_message_id = await _get_dashboard_message_id()

        if old_message_id:
            logger.info(f"🗑 Попытка удаления старого дэшборда ID: {old_message_id}")
            try:
                await asyncio.wait_for(
                    bot.delete_message(
                        chat_id=config.NEWS_CHANNEL_ID,
                        message_id=old_message_id,
                    ),
                    timeout=10.0,
                )
            except Exception as e:
                logger.debug(f"Старое сообщение дэшборда {old_message_id} не удалено: {e}")

        # 2. Собираем свежие данные и отправляем новое сообщение
        combined_data = _get_combined_data(liq_aggregator, market_aggregator, use_cache=False)
        text = DashboardFormatter.compile_dashboard(combined_data, window_minutes=15)

        msg = await asyncio.wait_for(
            bot.send_message(
                chat_id=config.NEWS_CHANNEL_ID,
                text=text,
                parse_mode="HTML",
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            ),
            timeout=10.0,
        )

        # 3. Закрепляем и сохраняем ID
        try:
            await asyncio.wait_for(
                bot.pin_chat_message(
                    chat_id=config.NEWS_CHANNEL_ID,
                    message_id=msg.message_id,
                ),
                timeout=10.0,
            )
        except Exception as e:
            logger.warning(f"Не удалось закрепить сообщение: {e}")

        await _set_dashboard_message_id(msg.message_id)
        await _set_last_summary_at()

        _last_data = combined_data
        _last_update_ts = time.time()
        logger.info(f"✅ Дэшборд успешно пересоздан. Новый ID: {msg.message_id}")
        return msg.message_id
    finally:
        _dashboard_recreate_in_progress = False

async def dashboard_worker(bot: Bot, liq_aggregator, market_aggregator):
    """
    Фоновый воркер для автоматического обновления закрепленного дэшборда в VIP-канале.
    """
    if config.NEWS_CHANNEL_ID is None:
        logger.warning("Дэшборд отключен: NEWS_CHANNEL_ID не задан.")
        return

    logger.info("🚀 Dashboard worker запущен.")
    initial_message_id = await _get_dashboard_message_id()
    logger.info(f"📊 Начальный ID дэшборда из metadata: {initial_message_id}")
    
    while True:
        try:
            if _dashboard_recreate_in_progress:
                await asyncio.sleep(1)
                continue

            message_id = await _get_dashboard_message_id()
            
            if message_id is None:
                await recreate_dashboard_logic(bot, liq_aggregator, market_aggregator)
            else:
                try:
                    combined_data = _get_combined_data(liq_aggregator, market_aggregator, use_cache=True)
                    text = DashboardFormatter.compile_dashboard(combined_data, window_minutes=15)

                    await asyncio.wait_for(
                        bot.edit_message_text(
                            chat_id=config.NEWS_CHANNEL_ID,
                            message_id=message_id,
                            text=text,
                            parse_mode="HTML",
                            link_preview_options=LinkPreviewOptions(is_disabled=True)
                        ),
                        timeout=10.0
                    )
                    await _set_last_summary_at()
                    
                except asyncio.TimeoutError:
                    logger.error("❌ Таймаут при редактировании дэшборда (10 сек).")
                    
                except TelegramForbiddenError:
                    logger.error(f"❌ Бот не имеет прав для редактирования сообщений в канале {config.NEWS_CHANNEL_ID}. Проверьте права администратора.")
                    
                except TelegramBadRequest as e:
                    error_msg = str(e).lower()
                    
                    # Self-healing: если сообщение не найдено или его нельзя редактировать
                    if "message to edit not found" in error_msg:
                        logger.error(f"❌ Сообщение дэшборда {message_id} не найдено. Пересоздаю.")
                        await recreate_dashboard_logic(bot, liq_aggregator, market_aggregator)
                    
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
