import unittest

import numpy as np

from src.services.indicators.rsi import RSIIndicator


class TestRSIIndicator(unittest.TestCase):
    def test_calculate_rsi_local_matches_wilder_reference(self) -> None:
        # Классический набор цен из примера Уайлдера: первый RSI(14) равен 70.46.
        prices = [
            44.34,
            44.09,
            44.15,
            43.61,
            44.33,
            44.83,
            45.10,
            45.42,
            45.84,
            46.08,
            45.89,
            46.03,
            45.61,
            46.28,
            46.28,
        ]

        self.assertEqual(RSIIndicator.calculate_rsi_local(prices, 14), 70.46)

    def test_calculate_rsi_local_accepts_numpy_array(self) -> None:
        prices = np.array([44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84, 46.08, 45.89, 46.03, 45.61, 46.28, 46.28], dtype=np.float64)

        self.assertEqual(RSIIndicator.calculate_rsi_local(prices, 14), 70.46)

    def test_calculate_rsi_local_returns_none_for_short_input(self) -> None:
        self.assertIsNone(RSIIndicator.calculate_rsi_local([1.0, 2.0, 3.0], 14))

    def test_calculate_rsi_local_returns_100_when_average_loss_is_zero(self) -> None:
        prices = [float(value) for value in range(1, 21)]

        self.assertEqual(RSIIndicator.calculate_rsi_local(prices, 14), 100.0)


if __name__ == "__main__":
    unittest.main()
