import logging
import pandas as pd
from pybit.unified_trading import HTTP

logger = logging.getLogger(__name__)

class RSIIndicator:
    def __init__(self):
        # Используем HTTP клиент для запросов к свечам
        self.http = HTTP(testnet=False)

    async def fetch_rsi(self, symbol: str, interval: int = 5, period: int = 14) -> float | None:
        """Получает RSI для монеты через REST API."""
        try:
            # Запрашиваем 50 свечей, чтобы расчет RSI за 14 периодов был точным
            # Выполняем в executor, так как pybit-HTTP может быть блокирующим асинхронность
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, 
                lambda: self.http.get_kline(
                    category="linear",
                    symbol=symbol,
                    interval=str(interval),
                    limit=50
                )
            )

            if response.get("retCode") != 0:
                return None

            # Извлекаем цены закрытия (Index 4 в Bybit Kline)
            prices = [float(candle[4]) for candle in response["result"]["list"]]
            prices.reverse() # Bybit отдает от новых к старым, нам нужно наоборот
            
            df = pd.DataFrame(prices, columns=["close"])
            
            # Расчет RSI
            delta = df["close"].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            last_rsi = rsi.iloc[-1]
            return round(float(last_rsi), 2)

        except Exception as e:
            logger.error(f"Ошибка расчета RSI для {symbol}: {e}")
            return None

import asyncio # Для run_in_executor