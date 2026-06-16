import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.models import ChannelSettings

logger = logging.getLogger(__name__)

class ChannelService:
    # Глобальный кэш настроек в оперативной памяти
    _cached_settings: ChannelSettings | None = None

    @classmethod
    async def get_settings(cls, session: AsyncSession) -> ChannelSettings:
        """
        Получает настройки канала. 
        Сначала проверяет кэш. Если кэш пуст — лезет в БД.
        Если в БД нет записи (первый запуск) — создает её.
        """
        if cls._cached_settings is not None:
            return cls._cached_settings
        
        try:
            result = await session.execute(select(ChannelSettings).where(ChannelSettings.id == 1))
            settings = result.scalar_one_or_none()
            
            if not settings:
                # Инициализация первой записи
                settings = ChannelSettings(id=1)
                session.add(settings)
                await session.commit()
                await session.refresh(settings)
                logger.info("Создана базовая запись настроек канала в БД.")
            
            cls._cached_settings = settings
            return settings
        except Exception as e:
            logger.error(f"Ошибка при получении настроек канала: {e}")
            # Возвращаем дефолтный объект, чтобы бот не упал при сбое БД
            return ChannelSettings()

    @classmethod
    async def update_settings(cls, session: AsyncSession, **kwargs) -> ChannelSettings:
        """
        Универсальный метод для обновления любых полей настроек.
        Пример вызова: await ChannelService.update_settings(session, threshold=50000.0, is_active=False)
        """
        try:
            settings = await cls.get_settings(session)
            
            for key, value in kwargs.items():
                if hasattr(settings, key):
                    setattr(settings, key, value)
            
            await session.commit()
            cls._cached_settings = settings # Мгновенно обновляем кэш
            return settings
        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка при обновлении настроек канала: {e}")
            return cls._cached_settings or ChannelSettings()

    @classmethod
    def get_cached_settings(cls) -> ChannelSettings:
        """
        Мгновенный синхронный доступ к настройкам. 
        Используется в высоконагруженных местах (например, в анализаторе), 
        чтобы вообще не тратить время на await и запросы.
        """
        if cls._cached_settings is None:
            return ChannelSettings()
        return cls._cached_settings
    
    @classmethod
    async def set_dashboard_id(cls, session: AsyncSession, message_id: int | None):
        """Хелпер специально для сохранения ID сообщения Дэшборда."""
        await cls.update_settings(session, dashboard_message_id=message_id)

    @classmethod
    async def update_last_summary_time(cls, session: AsyncSession, time_val):
        """Хелпер для обновления времени последнего отчета (Market Pulse)."""
        await cls.update_settings(session, last_summary_at=time_val)