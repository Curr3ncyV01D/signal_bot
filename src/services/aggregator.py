import asyncio
import logging
from collections import deque
from datetime import datetime, timezone
from src.core.config import config

logger = logging.getLogger(__name__)

class LiquidationAggregator:
    def __init__(self):
        # Структура: { "BTCUSDT": deque([(datetime, value, side), ...]) }
        self.history = {}

    def add_event(self, symbol: str, value: float, side: str):
        """Добавляет событие в память"""
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if symbol not in self.history:
            self.history[symbol] = deque()
        
        self.history[symbol].append((now, value, side))

    def get_metrics(self, symbol: str, side: str):
        """Отдает сразу все метрики за 1 проход по памяти"""
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        events = self.history.get(symbol, [])

        sum_5m = 0.0
        sum_1h = 0.0
        cascade_count = 0

        # Считаем суммы и каскады с конца (от свежих к старым)
        for date, value, event_side in reversed(events):
            if event_side != side:
                continue

            delta = (now - date).total_seconds()
            
            if delta > config.WINDOW_VOLUME_1H:
                break # Всё, дальше идут записи старше часа, они нам не нужны
            
            sum_1h += value
            if delta <= config.WINDOW_SQUEEZE_5M: 
                sum_5m += value
                if delta <= config.WINDOW_CASCADE: 
                    cascade_count += 1


        return sum_5m, sum_1h, cascade_count

    def load_historical_data(self, data):
        """Загружает исторические данные из БД в оперативную память"""
        count = 0
        for liq in data:
            if liq.symbol not in self.history:
                self.history[liq.symbol] = deque()
            
            # Определяем side_label (как в воркере)
            side_label = "SHORT" if liq.side == "Buy" else "LONG"
            
            self.history[liq.symbol].append((liq.timestamp, liq.value, side_label))
            count += 1
        logger.info(f"Оперативная память прогрета: загружено {count} записей.")

    async def cleanup_task(self):
        """Фоновая задача: удаляет из памяти всё, что старше 1 часа, чтобы не забивать ОЗУ"""
        while True:
            await asyncio.sleep(60) # Проверяем раз в минуту
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            for symbol, events in self.history.items():
                # Пока в начале очереди есть старые элементы - удаляем их
                while events and (now - events[0][0]).total_seconds() > config.WINDOW_1H_SEC:
                    events.popleft()

aggregator = LiquidationAggregator()