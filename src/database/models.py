from datetime import datetime
from .functions import get_utc_now
from sqlalchemy import BigInteger, String, Float, DateTime, Boolean, ForeignKey, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # Telegram ID
    username: Mapped[str] = mapped_column(String, nullable=True)
    language_code: Mapped[str] = mapped_column(String(2), default="ru")
    is_setup_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=get_utc_now)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)

    # --- Подписка и Кошелёк ---
    subscription_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)
    last_renewal_attempt: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)
    last_expiry_warning_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)
    auto_renewal: Mapped[bool] = mapped_column(Boolean, default=True)
    is_trial_used: Mapped[bool] = mapped_column(Boolean, default=False)
    balance: Mapped[float] = mapped_column(Float, default=0.0)
    referrer_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)

    # Ликвидации (Аналитика)
    threshold: Mapped[float] = mapped_column(Float, default=15000.0) 
    threshold_cascade: Mapped[float] = mapped_column(Float, default=25000.0) 

    threshold_mode: Mapped[str] = mapped_column(String(20), default="PERCENT")
    threshold_mcap_pct: Mapped[float] = mapped_column(Float, default=0.01)
    threshold_mcap_usd_min: Mapped[float] = mapped_column(Float, default=10000.0)
    threshold_cascade_mcap_pct: Mapped[float] = mapped_column(Float, default=0.015)
    threshold_cascade_mcap_usd_min: Mapped[float] = mapped_column(Float, default=20000.0)

    alert_cascade: Mapped[bool] = mapped_column(Boolean, default=True)
    alert_volume: Mapped[bool] = mapped_column(Boolean, default=True)
    alert_squeeze: Mapped[bool] = mapped_column(Boolean, default=True)
    alert_longs: Mapped[bool] = mapped_column(Boolean, default=True)
    alert_shorts: Mapped[bool] = mapped_column(Boolean, default=True)

    # Открытый интерес (OI)
    alert_oi: Mapped[bool] = mapped_column(Boolean, default=True)
    threshold_oi_percent: Mapped[float] = mapped_column(Float, default=6.0)
    threshold_oi_value: Mapped[float] = mapped_column(Float, default=500000.0)

    # CVD и RSI
    alert_cvd: Mapped[bool] = mapped_column(Boolean, default=True)
    alert_rsi: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Отношения
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="user")
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="user")


class UserEvent(Base):
    __tablename__ = "user_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    event_data: Mapped[str] = mapped_column(String(255), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=get_utc_now, index=True, nullable=False)


class SystemMetadata(Base):
    __tablename__ = "system_metadata"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(String(1024), nullable=False)


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

    # Отношения
    user: Mapped["User"] = relationship(back_populates="transactions")


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True, nullable=False)
    amount_actual: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    amount_expected: Mapped[float] = mapped_column(Float, nullable=False)
    payload: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False) # PENDING, PAID, PARTIAL, EXPIRED
    is_reminder_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=get_utc_now, nullable=False)
    external_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(20), default="CRYPTOMUS", nullable=False)
    address: Mapped[str | None] = mapped_column(String(128), nullable=True)
    network: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Отношения
    user: Mapped["User"] = relationship(back_populates="invoices")


class CoinFundamental(Base):
    __tablename__ = "coin_fundamentals"

    symbol: Mapped[str] = mapped_column(String(20), primary_key=True) # Базовый тикер (BTC, PEPE)
    circulating_supply: Mapped[float] = mapped_column(Float, nullable=False)
    cg_id: Mapped[str | None] = mapped_column(String(100), nullable=True) # CoinGecko ID
    last_updated: Mapped[datetime] = mapped_column(
        DateTime, 
        default=get_utc_now, 
        onupdate=get_utc_now
    )
