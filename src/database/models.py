from datetime import datetime
from .functions import get_utc_now
from sqlalchemy import BigInteger, String, Float, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # Telegram ID
    username: Mapped[str] = mapped_column(String, nullable=True)
    threshold: Mapped[float] = mapped_column(Float, default=10000.0) # Порог в долларах
    threshold_cascade: Mapped[float] = mapped_column(Float, default=5000.0) 
    created_at: Mapped[datetime] = mapped_column(DateTime, default=get_utc_now)
    alert_cascade: Mapped[bool] = mapped_column(default=True)
    alert_volume: Mapped[bool] = mapped_column(default=True)
    alert_squeeze: Mapped[bool] = mapped_column(default=True)

class Liquidation(Base):
    __tablename__ = "liquidations"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True) # Тикер, например BTCUSDT
    side: Mapped[str] = mapped_column(String(10)) # Buy или Sell
    price: Mapped[float] = mapped_column(Float) # Цена ликвидации
    qty: Mapped[float] = mapped_column(Float)   # Количество монет
    value: Mapped[float] = mapped_column(Float, index=True) # Объем в $ (price * qty)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=get_utc_now, index=True)
