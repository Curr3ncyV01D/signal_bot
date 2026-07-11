import asyncio
import logging
from datetime import datetime, timedelta, timezone
from src.database.session import async_session
from src.database.crud.liq_service import delete_old_liquidations
from src.database.crud.stats_service import delete_old_user_events

logger = logging.getLogger(__name__)

async def retention_policy_worker(
    hours: int = 4,
    interval_hours: int = 1,
    event_retention_days: int = 30,
    events_interval_hours: int = 24,
):
    """
    Фоновая задача для периодической очистки старых записей из БД.
    :param hours: Возраст записей для удаления (в часах)
    :param interval_hours: Интервал запуска очистки (в часах)
    :param event_retention_days: Возраст событий пользователей для удаления (в днях)
    :param events_interval_hours: Интервал запуска очистки событий (в часах)
    """
    logger.info(
        "Retention Policy запущен: ликвидации очищаются каждые %sч для записей старше %sч, "
        "user_events очищаются каждые %sч для записей старше %sд.",
        interval_hours,
        hours,
        events_interval_hours,
        event_retention_days,
    )
    next_events_cleanup_at: datetime | None = None
    
    while True:
        try:
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            async with async_session() as session:
                deleted_count = await delete_old_liquidations(session, hours=hours)
                if deleted_count > 0:
                    logger.debug(f"Retention Policy: успешно удалено {deleted_count} старых ликвидаций.")
                else:
                    logger.debug("Retention Policy: старых ликвидаций для удаления не найдено.")

                if next_events_cleanup_at is None or now >= next_events_cleanup_at:
                    deleted_events_count = await delete_old_user_events(
                        session,
                        days=event_retention_days,
                    )
                    if deleted_events_count > 0:
                        logger.debug(
                            "Retention Policy: успешно удалено %s старых событий пользователей.",
                            deleted_events_count,
                        )
                    else:
                        logger.debug("Retention Policy: старых событий пользователей для удаления не найдено.")

                    next_events_cleanup_at = now + timedelta(hours=events_interval_hours)
                    logger.debug(
                        "Следующая очистка user_events запланирована на %s",
                        next_events_cleanup_at.strftime("%Y-%m-%d %H:%M:%S"),
                    )
                
                next_run = now + timedelta(hours=interval_hours)
                logger.debug(f"Следующая очистка базы запланирована на {next_run.strftime('%H:%M:%S')}")

        except Exception as e:
            logger.error(f"Ошибка в Retention Policy воркере: {e}")
        
        # Ожидаем указанный интервал (переводим часы в секунды)
        await asyncio.sleep(interval_hours * 3600)
