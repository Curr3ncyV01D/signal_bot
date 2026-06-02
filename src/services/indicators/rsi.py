import logging
import pandas as pd
from src.core.config import config

logger = logging.getLogger(__name__)

class RSIIndicator:
    @staticmethod
    def calculate_rsi_local(prices: list[float], period: int = 14) -> float | None:
        """Считает RSI локально по списку цен в оперативной памяти (0 секунд ожидания сети)"""
        try:
            if len(prices) < period + 1:
                return None

            df = pd.DataFrame(prices, columns=["close"])
            
            # Расчет RSI через относительную силу
            delta = df["close"].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            
            # Защита от деления на ноль при флете
            loss = loss.replace(0, 0.00001)
            
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            val = rsi.iloc[-1]
            return round(float(val), 2) if not pd.isna(val) else None

        except Exception as e:
            logger.error(f"Ошибка локального расчета RSI: {e}")
            return None

# Оставляем синглтон для обратной совместимости
rsi_indicator = RSIIndicator()