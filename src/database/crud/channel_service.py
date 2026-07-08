import logging
from dataclasses import asdict, dataclass, fields
from datetime import datetime
import sqlalchemy as sa
from sqlalchemy import BigInteger, Boolean, DateTime, Float, Integer, MetaData, String, Table, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

channel_settings_table = Table(
    "channel_settings",
    MetaData(),
    sa.Column("id", Integer, primary_key=True),
    sa.Column("is_active", Boolean, nullable=False),
    sa.Column("threshold", Float, nullable=False),
    sa.Column("threshold_cascade", Float, nullable=False),
    sa.Column("alert_cascade", Boolean, nullable=False),
    sa.Column("alert_volume", Boolean, nullable=False),
    sa.Column("alert_squeeze", Boolean, nullable=False),
    sa.Column("alert_longs", Boolean, nullable=False),
    sa.Column("alert_shorts", Boolean, nullable=False),
    sa.Column("threshold_vol_pct", Float, nullable=False),
    sa.Column("threshold_mode", String(20), nullable=False),
    sa.Column("threshold_mcap_pct", Float, nullable=False),
    sa.Column("threshold_mcap_usd_min", Float, nullable=False),
    sa.Column("threshold_cascade_mcap_pct", Float, nullable=False),
    sa.Column("threshold_cascade_mcap_usd_min", Float, nullable=False),
    sa.Column("alert_oi", Boolean, nullable=False),
    sa.Column("threshold_oi_percent", Float, nullable=False),
    sa.Column("threshold_oi_value", Float, nullable=False),
    sa.Column("alert_cvd", Boolean, nullable=False),
    sa.Column("alert_rsi", Boolean, nullable=False),
    sa.Column("dashboard_message_id", BigInteger, nullable=True),
    sa.Column("last_summary_at", DateTime, nullable=True),
)

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
    def from_mapping(cls, row: dict):
        data = {}
        for field in fields(cls):
            if field.name in row:
                data[field.name] = row[field.name]
        return cls(**data)

class ChannelService:
    # Глобальный кэш настроек в оперативной памяти
    _cached_settings: ChannelSettingsData | None = None

    @staticmethod
    def _default_payload() -> dict:
        return asdict(ChannelSettingsData())

    @classmethod
    async def get_settings(cls, session: AsyncSession) -> ChannelSettingsData:
        """
        Получает настройки канала. 
        Сначала проверяет кэш. Если кэш пуст — лезет в БД.
        Если в БД нет записи (первый запуск) — создает её.
        """
        try:
            result = await session.execute(
                select(channel_settings_table).where(channel_settings_table.c.id == 1)
            )
            row = result.mappings().one_or_none()

            if row is None:
                default_payload = cls._default_payload()
                await session.execute(channel_settings_table.insert().values(**default_payload))
                await session.commit()
                logger.info("Создана базовая запись настроек канала в БД.")
                cls._cached_settings = ChannelSettingsData(**default_payload)
                return cls._cached_settings

            cls._cached_settings = ChannelSettingsData.from_mapping(dict(row))
            return cls._cached_settings
        except Exception as e:
            logger.warning(
                "Не удалось получить настройки канала. "
                "Вероятно, переходная стадия между Фазой 1 и Фазой 2: %s",
                e,
            )
            return cls._cached_settings or ChannelSettingsData()

    @classmethod
    async def update_settings(cls, session: AsyncSession, **kwargs) -> ChannelSettingsData:
        """
        Универсальный метод для обновления любых полей настроек.
        """
        try:
            allowed_keys = {field.name for field in fields(ChannelSettingsData)}
            update_payload = {key: value for key, value in kwargs.items() if key in allowed_keys}
            if not update_payload:
                return cls._cached_settings or ChannelSettingsData()

            result = await session.execute(
                select(channel_settings_table).where(channel_settings_table.c.id == 1)
            )
            row = result.mappings().one_or_none()

            if row is None:
                payload = cls._default_payload()
                payload.update(update_payload)
                await session.execute(channel_settings_table.insert().values(**payload))
                await session.commit()
                cls._cached_settings = ChannelSettingsData(**payload)
                return cls._cached_settings

            await session.execute(
                channel_settings_table.update()
                .where(channel_settings_table.c.id == 1)
                .values(**update_payload)
            )
            await session.commit()

            refreshed = await session.execute(
                select(channel_settings_table).where(channel_settings_table.c.id == 1)
            )
            refreshed_row = refreshed.mappings().one_or_none()
            if refreshed_row is None:
                cls._cached_settings = cls._cached_settings or ChannelSettingsData()
                return cls._cached_settings

            cls._cached_settings = ChannelSettingsData.from_mapping(dict(refreshed_row))
            return cls._cached_settings
        except Exception as e:
            await session.rollback()
            logger.warning(
                "Не удалось обновить настройки канала. "
                "Вероятно, таблица уже удалена в рамках Фазы 1: %s",
                e,
            )
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
