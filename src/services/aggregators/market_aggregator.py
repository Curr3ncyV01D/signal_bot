import logging
from collections import deque
from datetime import datetime, timezone
import asyncio

logger = logging.getLogger(__name__)

class MarketAggregator:
    def __init__(self):
        # Структура: { "BTCUSDT": deque([(ts, price, oi), ...], maxlen=61) }
        # Храним 60 минут истории для расчета дельты
        self.history: dict[str, deque] = {}
        # Текущие снапшоты для быстрого доступа
        self.snapshots: dict[str, dict] = {}

    def update(self, symbol: str, price: float, oi: float, funding: float, l_s_ratio: str | None = None):
        now = datetime.now(timezone.utc).timestamp()
        
        # Обновляем текущий снапшот
        self.snapshots[symbol] = {
            "price": price,
            "oi": oi,
            "funding": funding,
            "l_s_ratio": l_s_ratio,
            "ts": now
        }

        # Добавляем в историю для расчета изменений (раз в минуту)
        if symbol not in self.history:
            self.history[symbol] = deque(maxlen=61)
        
        last_history = self.history[symbol][-1] if self.history[symbol] else None
        # Записываем в историю, если прошло более 60 секунд с последней записи
        if not last_history or (now - last_history[0]) >= 60:
            self.history[symbol].append((now, price, oi))

    def get_market_data(self, symbol: str, window_minutes: int = 5):
        """Возвращает текущие данные и изменение OI/Price за N минут."""
        current = self.snapshots.get(symbol)
        if not current:
            return None

        hist = self.history.get(symbol, [])
        if not hist:
            return {**current, "oi_change_pct": 0.0, "price_change_pct": 0.0}

        # Ищем запись максимально близкую к T - window_minutes
        target_ts = current["ts"] - (window_minutes * 60)
        old_record = hist[0]
        for rec in reversed(hist):
            if rec[0] <= target_ts:
                old_record = rec
                break
        
        old_price, old_oi = old_record[1], old_record[2]
        
        oi_change_pct = ((current["oi"] - old_oi) / old_oi * 100) if old_oi > 0 else 0.0
        price_change_pct = ((current["price"] - old_price) / old_price * 100) if old_price > 0 else 0.0
        oi_change_value = current["oi"] - old_oi

        return {
            **current,
            "oi_change_pct": round(oi_change_pct, 2),
            "oi_change_value": round(oi_change_value, 2),
            "price_change_pct": round(price_change_pct, 2)
        }