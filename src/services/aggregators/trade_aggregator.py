import logging
from collections import deque
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class TradeAggregator:
    def __init__(self):
        # { "BTCUSDT": deque([min_delta1, min_delta2, ...], maxlen=61) }
        self.buckets: dict[str, deque] = {}
        # Временное хранилище для текущей (незавершенной) минуты
        self.current_minute_data: dict[str, dict] = {} 

    def add_trades(self, symbol: str, trades: list[dict]):
        now_minute = int(datetime.now(timezone.utc).timestamp() // 60)
        
        if symbol not in self.current_minute_data:
            self._rotate_bucket(symbol, now_minute)

        # Если минута сменилась — сбрасываем бакет в историю
        if self.current_minute_data[symbol]["minute"] != now_minute:
            self._rotate_bucket(symbol, now_minute)

        for t in trades:
            side = t.get("S") or t.get("side")
            try:
                value = float(t.get("p", 0)) * float(t.get("v", 0))
                if side == "Buy":
                    self.current_minute_data[symbol]["buy_vol"] += value
                else:
                    self.current_minute_data[symbol]["sell_vol"] += value
            except: continue

    def _rotate_bucket(self, symbol: str, new_minute: int):
        if symbol in self.current_minute_data:
            data = self.current_minute_data[symbol]
            delta = data["buy_vol"] - data["sell_vol"]
            
            if symbol not in self.buckets:
                self.buckets[symbol] = deque(maxlen=61)
            self.buckets[symbol].append({"buy": data["buy_vol"], "sell": data["sell_vol"], "delta": delta})
        
        self.current_minute_data[symbol] = {"minute": new_minute, "buy_vol": 0.0, "sell_vol": 0.0}

    def get_cvd_metrics(self, symbol: str, minutes: int = 5):
        """Считает More Buys/Sells за последние N минут."""
        hist = self.buckets.get(symbol, [])
        if not hist: return 0.0, 0.0, 0.0
        
        # Берем последние N минутных бакетов
        target_buckets = list(hist)[-minutes:]
        total_buy = sum(b["buy"] for b in target_buckets)
        total_sell = sum(b["sell"] for b in target_buckets)
        
        # Добавляем данные текущей (еще не закрытой) минуты для точности
        if symbol in self.current_minute_data:
            total_buy += self.current_minute_data[symbol]["buy_vol"]
            total_sell += self.current_minute_data[symbol]["sell_vol"]

        return total_buy, total_sell, (total_buy - total_sell)