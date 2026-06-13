from datetime import datetime
from .functions import get_utc_now
from sqlalchemy import BigInteger, String, Float, DateTime, Boolean, ForeignKey, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # Telegram ID
    username: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=get_utc_now)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)

    # --- Подписка и Кошелёк ---
    subscription_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)
    is_trial_used: Mapped[bool] = mapped_column(Boolean, default=False)
    balance: Mapped[float] = mapped_column(Float, default=0.0)
    referrer_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)

    # Ликвидации (Аналитика)
    threshold: Mapped[float] = mapped_column(Float, default=10000.0) 
    threshold_cascade: Mapped[float] = mapped_column(Float, default=5000.0) 
    alert_cascade: Mapped[bool] = mapped_column(Boolean, default=True)
    alert_volume: Mapped[bool] = mapped_column(Boolean, default=True)
    alert_squeeze: Mapped[bool] = mapped_column(Boolean, default=True)

    # Открытый интерес (OI)
    alert_oi: Mapped[bool] = mapped_column(Boolean, default=True)
    threshold_oi_percent: Mapped[float] = mapped_column(Float, default=5.0)
    threshold_oi_value: Mapped[float] = mapped_column(Float, default=500000.0)

    # CVD и RSI
    alert_cvd: Mapped[bool] = mapped_column(Boolean, default=True)
    alert_rsi: Mapped[bool] = mapped_column(Boolean, default=True)


class ChannelSettings(Base):
    __tablename__ = "channel_settings"
    
    # Всегда id=1 для глобальных настроек
    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    
    # Главный тумблер канала
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Ликвидация
    threshold: Mapped[float] = mapped_column(Float, default=100000.0) # Пороги выше для канала
    threshold_cascade: Mapped[float] = mapped_column(Float, default=50000.0)
    alert_cascade: Mapped[bool] = mapped_column(Boolean, default=True)
    alert_volume: Mapped[bool] = mapped_column(Boolean, default=True)
    alert_squeeze: Mapped[bool] = mapped_column(Boolean, default=True)

    # Открытый интерес (OI)
    alert_oi: Mapped[bool] = mapped_column(Boolean, default=True)
    threshold_oi_percent: Mapped[float] = mapped_column(Float, default=10.0)
    threshold_oi_value: Mapped[float] = mapped_column(Float, default=1000000.0)

    # CVD и RSI
    alert_cvd: Mapped[bool] = mapped_column(Boolean, default=True)
    alert_rsi: Mapped[bool] = mapped_column(Boolean, default=True)

    # Технические поля канала
    dashboard_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_summary_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Liquidation(Base):
    __tablename__ = "liquidations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True) # Тикер, например BTCUSDT
    side: Mapped[str] = mapped_column(String(10)) # Buy или Sell
    price: Mapped[float] = mapped_column(Float) # Цена ликвидации
    qty: Mapped[float] = mapped_column(Float)   # Количество монет
    value: Mapped[float] = mapped_column(Float, index=True) # Объем в $ (price * qty)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=get_utc_now, index=True)


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False) # DEPOSIT, WITHDRAW, REWARD
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=get_utc_now, index=True, nullable=False)


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    crypto_pay_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False) # PENDING, PAID, EXPIRED
    created_at: Mapped[datetime] = mapped_column(DateTime, default=get_utc_now, nullable=False)