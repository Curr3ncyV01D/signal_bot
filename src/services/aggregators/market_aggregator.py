import logging
from collections import deque
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class MarketAggregator:
    def __init__(self):
        # Структура: { "BTCUSDT": deque([(ts, price, oi), ...], maxlen=61) }
        self.history: dict[str, deque] = {}
        # Текущие снапшоты для быстрого доступа
        self.snapshots: dict[str, dict] = {}
        
        # НОВОЕ: Внутрипамятное хранилище цен для RSI (раз в 5 минут)
        self.rsi_prices: dict[str, deque[float]] = {}
        self.rsi_bars: dict[str, int] = {} # Хранит ID текущего 5-минутного бара

    def update(self, symbol: str, price: float | None, oi: float | None, funding: float | None):
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

        # 2. НОВОЕ: Логика формирования 5-минутных свечей для RSI в ОЗУ
        if price is not None and price > 0:
            now_bar = int(now // 300) # ID текущего 5-минутного интервала
            
            if symbol not in self.rsi_prices:
                self.rsi_prices[symbol] = deque(maxlen=30) # Храним 30 цен закрытия
                self.rsi_bars[symbol] = now_bar
                self.rsi_prices[symbol].append(price)
            elif self.rsi_bars[symbol] != now_bar:
                # Бар сменился. Добавляем цену как закрытие нового бара
                self.rsi_prices[symbol].append(price)
                self.rsi_bars[symbol] = now_bar
            else:
                # Мы внутри того же 5-минутного бара. Обновляем текущую "живую" цену закрытия
                if self.rsi_prices[symbol]:
                    self.rsi_prices[symbol][-1] = price

    def get_market_data(self, symbol: str, window_minutes: int = 5):
        """Возвращает текущие данные и изменение OI/Price за N минут."""
        current = self.snapshots.get(symbol)
        hist = self.history.get(symbol, [])
        
        if not current:
            return None

        if not hist:
            return {
                **current, 
                "oi_change_pct": None, 
                "oi_change_value": None,
                "price_change_pct": None
            }
        
        now = current["ts"]
        if (now - hist[0][0]) < (window_minutes * 60):
            return {
                **current, 
                "oi_change_pct": None, 
                "oi_change_value": None,
                "price_change_pct": None
            }
            
        old_record = hist[0]
        target_ts = now - (window_minutes * 60)
        for rec in reversed(hist):
            if rec[0] <= target_ts:
                old_record = rec
                break
        
        old_price, old_oi = old_record[1], old_record[2]

        if old_oi == 0 or old_price == 0:
            return {**current, "oi_change_pct": None, "price_change_pct": None, "oi_change_value": 0}
        
        oi_change_value = current["oi"] - old_oi
        oi_change_pct = ((current["oi"] - old_oi) / old_oi * 100) if old_oi > 0 else 0.0
        price_change_pct = ((current["price"] - old_price) / old_price * 100) if old_price > 0 else 0.0

        return {
            **current,
            "oi_change_pct": round(oi_change_pct, 2),
            "oi_change_value": round(oi_change_value, 2),
            "price_change_pct": round(price_change_pct, 2)
        }