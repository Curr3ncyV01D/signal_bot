import logging
from dataclasses import dataclass, fields
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.models import ChannelSettings

logger = logging.getLogger(__name__)

@dataclass
class ChannelSettingsData:
    id: int = 1
    is_active: bool = True
    threshold: float = 100000.0
    threshold_cascade: float = 50000.0
    alert_cascade: bool = True
    alert_volume: bool = True
    alert_squeeze: bool = True
    alert_longs: bool = True
    alert_shorts: bool = True
    threshold_vol_pct: float = 0.0
    
    threshold_mode: str = "USD"
    threshold_mcap_pct: float = 0.005
    threshold_mcap_usd_min: float = 1000.0
    threshold_cascade_mcap_pct: float = 0.01
    threshold_cascade_mcap_usd_min: float = 5000.0

    alert_oi: bool = True
    threshold_oi_percent: float = 10.0
    threshold_oi_value: float = 1000000.0
    alert_cvd: bool = True
    alert_rsi: bool = True
    dashboard_message_id: int | None = None
    last_summary_at: datetime | None = None

    @classmethod
    def from_orm(cls, obj: ChannelSettings):
        data = {}
        for field in fields(cls):
            if hasattr(obj, field.name):
                data[field.name] = getattr(obj, field.name)
        return cls(**data)

class ChannelService:
    # Глобальный кэш настроек в оперативной памяти
    _cached_settings: ChannelSettingsData | None = None

    @classmethod
    async def get_settings(cls, session: AsyncSession) -> ChannelSettingsData:
        """
        Получает настройки канала. 
        Сначала проверяет кэш. Если кэш пуст — лезет в БД.
        Если в БД нет записи (первый запуск) — создает её.
        """
        try:
            result = await session.execute(select(ChannelSettings).where(ChannelSettings.id == 1))
            settings_orm = result.scalar_one_or_none()
            
            if not settings_orm:
                # Инициализация первой записи
                settings_orm = ChannelSettings(id=1)
                session.add(settings_orm)
                await session.commit()
                await session.refresh(settings_orm)
                logger.info("Создана базовая запись настроек канала в БД.")
            else:
                # Гарантируем актуальность данных из БД
                await session.refresh(settings_orm)
            
            # Конвертируем в plain object для кэша
            cls._cached_settings = ChannelSettingsData.from_orm(settings_orm)
            return cls._cached_settings
            
        except Exception as e:
            logger.error(f"Ошибка при получении настроек канала: {e}")
            # Возвращаем дефолтный объект из кэша или новый, чтобы бот не упал
            return cls._cached_settings or ChannelSettingsData()

    @classmethod
    async def update_settings(cls, session: AsyncSession, **kwargs) -> ChannelSettingsData:
        """
        Универсальный метод для обновления любых полей настроек.
        """
        try:
            # Получаем ORM объект для обновления
            result = await session.execute(select(ChannelSettings).where(ChannelSettings.id == 1))
            settings_orm = result.scalar_one_or_none()
            
            if not settings_orm:
                settings_orm = ChannelSettings(id=1)
                session.add(settings_orm)

            for key, value in kwargs.items():
                if hasattr(settings_orm, key):
                    setattr(settings_orm, key, value)
            
            await session.commit()
            await session.refresh(settings_orm)
            
            # Обновляем кэш
            cls._cached_settings = ChannelSettingsData.from_orm(settings_orm)
            return cls._cached_settings
        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка при обновлении настроек канала: {e}")
            return cls._cached_settings or ChannelSettingsData()

    @classmethod
    def get_cached_settings(cls) -> ChannelSettingsData:
        """
        Мгновенный синхронный доступ к настройкам. 
        """
        if cls._cached_settings is None:
            # Если кэш пуст, возвращаем дефолтный объект, но это не должно происходить после init
            return ChannelSettingsData()
        return cls._cached_settings
    
    @classmethod
    async def set_dashboard_id(cls, session: AsyncSession, message_id: int | None):
        """Хелпер специально для сохранения ID сообщения Дэшборда."""
        await cls.update_settings(session, dashboard_message_id=message_id)

    @classmethod
    async def update_last_summary_time(cls, session: AsyncSession, time_val):
        """Хелпер для обновления времени последнего отчета (Market Pulse)."""
        await cls.update_settings(session, last_summary_at=time_val)