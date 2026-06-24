import logging
import heapq
from typing import Any
from collections import deque
from datetime import datetime, timezone
from src.services.indicators.rsi import rsi_indicator

logger = logging.getLogger(__name__)

class MarketAggregator:
    def __init__(self) -> None:
        # Структура: { "BTCUSDT": deque([(ts, price, oi), ...], maxlen=61) }
        self.history: dict[str, deque[tuple[float, float, float]]] = {}
        # Текущие снапшоты для быстрого доступа
        self.snapshots: dict[str, dict[str, Any]] = {}
        # L1-кэш RSI: { "BTCUSDT": ((current_price, bars_count), rsi_value) }
        self._rsi_cache: dict[str, tuple[tuple[float, int], float | None]] = {}
        
        # НОВОЕ: Внутрипамятное хранилище цен для RSI (раз в 5 минут)
        self.rsi_prices: dict[str, deque[float]] = {}
        self.rsi_bars: dict[str, int] = {} # Хранит ID текущего 5-минутного бара

    @staticmethod
    def _get_window_record(
        hist: deque[tuple[float, float, float]] | None,
        now: float,
        window_minutes: int,
    ) -> tuple[float, float, float] | None:
        """Ищет ближайшую запись окна по индексу с локальным обходом соседей."""
        if not hist or window_minutes < 1:
            return None

        target_idx = -(window_minutes + 1)
        target_time = now - (window_minutes * 60)

        # 1. Попытка прямого доступа по индексу
        try:
            # Пытаемся взять целевой индекс
            direct_record = hist[target_idx]
            
            # Проверяем, насколько далеко мы от цели
            direct_diff = abs(direct_record[0] - target_time)
            if direct_diff <= 20:
                return direct_record

            # Если отклонение есть, ищем среди ближайших соседей
            best_record: tuple[float, float, float] | None = None
            best_diff = float("inf")

            for idx in range(target_idx - 2, target_idx + 3):
                try:
                    candidate = hist[idx]
                except IndexError:
                    continue

                candidate_diff = abs(candidate[0] - target_time)
                if candidate_diff < best_diff:
                    best_record = candidate
                    best_diff = candidate_diff

            if best_record and best_diff <= 45:
                return best_record

        except IndexError:
            # 2. Fallback Logic: Если данных мало, берем самую старую запись (hist[0])
            # Условие честности: возраст записи >= 120 секунд
            oldest = hist[0]
            if (now - oldest[0]) >= 120:
                return oldest
            
        return None

    def seed_history(self, symbol: str, prices: list[float], oi_points: list[tuple[int, float]] | None = None) -> None:
        """
        Предварительное наполнение истории цен и OI для устранения 'окна слепоты'.
        Генерирует синхронизированные таймстампы привязанные к началу минуты.
        """
        if not prices or len(self.history.get(symbol, [])) >= 2:
            return

        now = datetime.now(timezone.utc).timestamp()
        now_min = int(now // 60) * 60
        
        # Инициализируем историю, если её нет
        if symbol not in self.history:
            self.history[symbol] = deque(maxlen=61)
            
        self.history[symbol].clear()
        
        # Наполняем историю: ts привязаны к началу минут
        seed_data = prices[-60:]
        count = len(seed_data)
        
        # Подготовка данных OI для быстрого поиска
        # Сортируем по времени (Bybit обычно и так шлет от новых к старым, но на всякий случай)
        oi_sorted = sorted(oi_points, key=lambda x: x[0]) if oi_points else []

        for i, price in enumerate(seed_data):
            offset = (count - 1 - i)
            ts_sec = now_min - (offset * 60)
            ts_ms = ts_sec * 1000
            
            # Поиск ближайшего OI (размазываем последнее известное значение)
            # Ищем самый свежий OI, который меньше или равен текущему ts_ms
            current_oi = 0.0
            if oi_sorted:
                # Так как точек мало (15), линейный поиск допустим
                for timestamp, value in reversed(oi_sorted):
                    if timestamp <= ts_ms:
                        current_oi = value
                        break
                # Если не нашли (ts_ms меньше всех точек), берем самую старую
                if current_oi == 0.0 and oi_sorted:
                    current_oi = oi_sorted[0][1]

            self.history[symbol].append((float(ts_sec), float(price), float(current_oi)))

    def update(self, symbol: str, price: float | None, oi: float | None, funding: float | None) -> None:
        now = datetime.now(timezone.utc).timestamp()
        
        if symbol not in self.snapshots:
            self.snapshots[symbol] = {"price": 0.0, "oi": 0.0, "funding": 0.0, "ts": now}
        
        # Обновляем только если значение пришло (не None)
        if price is not None: self.snapshots[symbol]["price"] = price
        if oi is not None: self.snapshots[symbol]["oi"] = oi
        if funding is not None: self.snapshots[symbol]["funding"] = funding
        
        self.snapshots[symbol]["ts"] = now

        # 1. Запись истории для изменения ОИ (раз в минуту)
        if symbol not in self.history:
            self.history[symbol] = deque(maxlen=61)
        
        last_ts = self.history[symbol][-1][0] if self.history[symbol] else 0
        if now - last_ts >= 60:
            snap = self.snapshots[symbol]
            self.history[symbol].append((now, snap["price"], snap["oi"]))

        # 2. НОВОЕ: Логика формирования часовых свечей для RSI в ОЗУ
        if price is not None and price > 0:
            now_bar = int(now // 3600) # ID текущего часового интервала
            
            if symbol not in self.rsi_prices:
                self.rsi_prices[symbol] = deque(maxlen=50) # Храним 50 цен закрытия
                self.rsi_bars[symbol] = now_bar
                self.rsi_prices[symbol].append(price)
            elif self.rsi_bars[symbol] != now_bar:
                # Бар сменился. Добавляем цену как закрытие нового бара
                self.rsi_prices[symbol].append(price)
                self.rsi_bars[symbol] = now_bar
            else:
                # Мы внутри того же часового бара. Обновляем текущую "живую" цену закрытия
                if self.rsi_prices[symbol]:
                    self.rsi_prices[symbol][-1] = price

    def get_cached_rsi(self, symbol: str, period: int = 14) -> float | None:
        """Возвращает RSI из L1-кэша или вычисляет его при cache miss."""
        prices = self.rsi_prices.get(symbol)
        current_snap = self.snapshots.get(symbol)
        if not prices or not current_snap or len(prices) < period + 1:
            return None

        cached_rsi = self._rsi_cache.get(symbol)
        cache_key = (current_snap["price"], len(prices))
        if cached_rsi and cached_rsi[0] == cache_key:
            return cached_rsi[1]

        rsi_val = rsi_indicator.calculate_rsi_local(prices, period)
        self._rsi_cache[symbol] = (cache_key, rsi_val)
        return rsi_val

    def get_market_data(self, symbol: str, window_minutes: int = 5) -> dict[str, Any] | None:
        """Возвращает текущие данные и изменение OI/Price за N минут."""
        current = self.snapshots.get(symbol)
        if not current:
            return None

        hist = self.history.get(symbol)
        
        # Базовая структура при отсутствии истории (Холодный старт)
        result = {
            **current, 
            "oi_change_pct": None, 
            "oi_change_value": None,
            "price_change_pct": None
        }

        if not hist:
            return result
        
        now = current["ts"]
        old_record = self._get_window_record(hist, now, window_minutes)
        if old_record is None:
            return result
        
        old_price, old_oi = old_record[1], old_record[2]

        if old_oi == 0 or old_price == 0:
            return result
        
        oi_change_value = current["oi"] - old_oi
        oi_change_pct = ((current["oi"] - old_oi) / old_oi * 100)
        price_change_pct = ((current["price"] - old_price) / old_price * 100)

        result.update({
            "oi_change_pct": round(oi_change_pct, 2),
            "oi_change_value": round(oi_change_value, 2),
            "price_change_pct": round(price_change_pct, 2)
        })
        return result

    def get_market_rankings(self, window_minutes: int = 15, oi_limit: int = 20) -> dict[str, Any]:
        """
        Генерирует рыночные рейтинги (OI, RSI, BTC).
        """
        total_oi_current = 0.0
        total_oi_old = 0.0
        oi_data = []

        # 1. Агрегация OI по всем монетам
        for symbol, current_snap in self.snapshots.items():
            try:
                hist = self.history.get(symbol)
                old_record = self._get_window_record(hist, current_snap["ts"], window_minutes)
                if old_record is None:
                    continue

                current_oi = current_snap["oi"]
                old_oi = old_record[2]
                oi_pct = ((current_oi - old_oi) / old_oi * 100) if old_oi > 0 else 0.0
                oi_delta = current_oi - old_oi

                total_oi_current += current_oi
                total_oi_old += old_oi
                oi_data.append((symbol, round(oi_pct, 2), round(oi_delta, 2), round(current_oi, 2)))
            except Exception as e:
                logger.error(f"Ошибка агрегации OI для {symbol}: {e}")
                continue

        # 2. Сортировка OI и расчет итогов
        oi_up = []
        oi_down = []
        total_oi_pct_change = 0.0

        if oi_data:
            oi_up = heapq.nlargest(oi_limit, (d for d in oi_data if d[1] > 0), key=lambda x: x[1])
            oi_down = heapq.nlargest(oi_limit, (d for d in oi_data if d[1] < 0), key=lambda x: -x[1])
            
        if total_oi_old > 0:
            total_oi_pct_change = ((total_oi_current - total_oi_old) / total_oi_old * 100)

        # 3. RSI Heatmap
        rsi_overbought = []
        rsi_oversold = []
        
        for symbol, prices in self.rsi_prices.items():
            try:
                if len(prices) < 15:
                    continue

                rsi_val = self.get_cached_rsi(symbol, 14)
                if rsi_val is not None:
                    if rsi_val > 80:
                        rsi_overbought.append((symbol, rsi_val))
                    elif rsi_val < 20:
                        rsi_oversold.append((symbol, rsi_val))
            except Exception as e:
                logger.error(f"Ошибка расчета RSI Heatmap для {symbol}: {e}")
                continue
        
        rsi_overbought = heapq.nlargest(10, rsi_overbought, key=lambda x: x[1])
        rsi_oversold = heapq.nlargest(10, rsi_oversold, key=lambda x: -x[1])

        # 4. Данные BTCUSDT (Независимое получение цены - KISS)
        btc_snap = self.snapshots.get("BTCUSDT", {})
        btc_price = btc_snap.get("price", 0.0)
        
        # Динамику пытаемся получить отдельно
        btc_hist = self.get_market_data("BTCUSDT", 60)
        btc_change_1h = btc_hist.get("price_change_pct") if btc_hist else None

        return {
            "oi_up": oi_up,
            "oi_down": oi_down,
            "total_oi_current": round(total_oi_current, 2),
            "total_oi_pct_change": round(total_oi_pct_change, 2) if total_oi_old > 0 else None,
            "rsi_overbought": rsi_overbought,
            "rsi_oversold": rsi_oversold,
            "btc_price": btc_price,
            "btc_change_1h": btc_change_1h
        }
