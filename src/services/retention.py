import asyncio
import logging
from datetime import datetime, timedelta, timezone
from src.database.session import async_session
from src.database.crud.liq_service import delete_old_liquidations

logger = logging.getLogger(__name__)

async def retention_policy_worker(hours: int = 4, interval_hours: int = 1):
    """
    Фоновая задача для периодической очистки старых записей из БД.
    :param hours: Возраст записей для удаления (в часах)
    :param interval_hours: Интервал запуска очистки (в часах)
    """
    logger.info(f"Retention Policy запущен: очистка каждые {interval_hours}ч для записей старше {hours}ч.")
    
    while True:
        try:
            async with async_session() as session:
                deleted_count = await delete_old_liquidations(session, hours=hours)
                if deleted_count > 0:
                    logger.debug(f"Retention Policy: успешно удалено {deleted_count} старых записей.")
                else:
                    logger.debug("Retention Policy: старых записей для удаления не найдено.")
                
                next_run = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=interval_hours)
                logger.debug(f"Следующая очистка базы запланирована на {next_run.strftime('%H:%M:%S')}")

        except Exception as e:
            logger.error(f"Ошибка в Retention Policy воркере: {e}")
        
        # Ожидаем указанный интервал (переводим часы в секунды)
        await asyncio.sleep(interval_hours * 3600)
