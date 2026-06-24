import logging
import numpy as np

logger = logging.getLogger(__name__)


class RSIIndicator:
    @staticmethod
    def calculate_rsi_numpy(prices: list[float] | np.ndarray, period: int = 14) -> float | None:
        """Считает RSI по методу Уайлдера (RMA)"""
        try:
            if period <= 0:
                return None

            prices_array = np.array(prices, dtype=np.float64)
            if prices_array.size < period + 1:
                return None

            deltas = np.diff(prices_array)
            gains = np.where(deltas > 0.0, deltas, 0.0)
            losses = np.where(deltas < 0.0, -deltas, 0.0)

            avg_gain = float(np.mean(gains[:period]))
            avg_loss = float(np.mean(losses[:period]))

            for idx in range(period, deltas.size):
                avg_gain = ((avg_gain * (period - 1)) + float(gains[idx])) / period
                avg_loss = ((avg_loss * (period - 1)) + float(losses[idx])) / period

            if avg_loss == 0.0:
                return 100.0

            rs = avg_gain / avg_loss
            rsi = 100.0 - (100.0 / (1.0 + rs))
            return round(float(rsi), 2) if np.isfinite(rsi) else None

        except Exception as e:
            logger.error(f"Ошибка локального расчета RSI: {e}")
            return None

    # Костыль для обратной совместимости(поменять на этапе рефакторинга проекта)
    @staticmethod
    def calculate_rsi_local(prices: list[float] | np.ndarray, period: int = 14) -> float | None:
        """Считает RSI локально по списку цен в оперативной памяти (0 секунд ожидания сети)."""
        return RSIIndicator.calculate_rsi_numpy(prices, period)

# Оставляем синглтон для обратной совместимости
rsi_indicator = RSIIndicator()
