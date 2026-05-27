from datetime import datetime
from .functions import get_utc_now
from sqlalchemy import BigInteger, String, Float, DateTime, Boolean
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # Telegram ID
    username: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=get_utc_now)

    # Ликвидации
    threshold: Mapped[float] = mapped_column(Float, default=10000.0) # Порог в долларах
    threshold_cascade: Mapped[float] = mapped_column(Float, default=5000.0) 
    alert_cascade: Mapped[bool] = mapped_column(default=True)
    alert_volume: Mapped[bool] = mapped_column(default=True)
    alert_squeeze: Mapped[bool] = mapped_column(default=True)

    # Открытый интерес (OI)
    alert_oi: Mapped[bool] = mapped_column(Boolean, default=True)
    threshold_oi_percent: Mapped[float] = mapped_column(Float, default=5.0) # От 5%
    threshold_oi_value: Mapped[float] = mapped_column(Float, default=500000.0) # От $0.5M

    # CVD и RSI
    alert_cvd: Mapped[bool] = mapped_column(Boolean, default=True)
    alert_rsi: Mapped[bool] = mapped_column(Boolean, default=True)

class Liquidation(Base):
    __tablename__ = "liquidations"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True) # Тикер, например BTCUSDT
    side: Mapped[str] = mapped_column(String(10)) # Buy или Sell
    price: Mapped[float] = mapped_column(Float) # Цена ликвидации
    qty: Mapped[float] = mapped_column(Float)   # Количество монет
    value: Mapped[float] = mapped_column(Float, index=True) # Объем в $ (price * qty)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=get_utc_now, index=True)
