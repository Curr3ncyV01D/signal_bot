import asyncio
import heapq
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
        sum_cascade = 0.0
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
                    sum_cascade += value
                    cascade_count += 1


        return sum_5m, sum_1h, sum_cascade, cascade_count

    def get_top_liquidations(self, window_minutes: int = 15, limit: int = 10) -> dict:
        """
        Возвращает топ монет по объему ликвидаций за указанное окно.
        """
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        window_seconds = window_minutes * 60
        
        longs_map = {}
        shorts_map = {}

        for symbol, events in self.history.items():
            try:
                if not events:
                    continue

                for date, value, side in reversed(events):
                    if (now - date).total_seconds() > window_seconds:
                        break
                    
                    if side == "LONG":
                        longs_map[symbol] = longs_map.get(symbol, 0.0) + value
                    elif side == "SHORT":
                        shorts_map[symbol] = shorts_map.get(symbol, 0.0) + value
            except Exception as e:
                logger.error(f"Ошибка агрегации ликвидаций для {symbol}: {e}")
                continue

        top_longs = heapq.nlargest(limit, longs_map.items(), key=lambda x: x[1])
        top_shorts = heapq.nlargest(limit, shorts_map.items(), key=lambda x: x[1])

        return {
            "longs": top_longs,
            "shorts": top_shorts
        }

    def load_historical_data(self, data):
        """Загружает исторические данные из БД в оперативную память"""
        count = 0
        for liq in data:
            if liq.symbol not in self.history:
                self.history[liq.symbol] = deque()
            
            # Определяем side_label (как в воркере)
            side_label = "LONG" if liq.side == "Buy" else "SHORT"
            
            self.history[liq.symbol].append((liq.timestamp, liq.value, side_label))
            count += 1
        logger.info(f"Оперативная память прогрета: загружено {count} записей.")

    async def cleanup_task(self):
        """
        Фоновая задача: удаляет старые данные и логирует процесс для отладки.
        """
        logger.info("✅ Фоновая очистка Aggregator запущена.")
        
        while True:
            try:
                await asyncio.sleep(60) 
                
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                total_removed = 0

                empty_symbols = []
                for symbol, events in self.history.items():
                    if not events:
                        empty_symbols.append(symbol)
                        continue

                    while events and (now - events[0][0]).total_seconds() > config.WINDOW_VOLUME_1H:
                        events.popleft()
                        total_removed += 1

                    if not events:
                        empty_symbols.append(symbol)

                for symbol in empty_symbols:
                    self.history.pop(symbol, None)
                
                if total_removed > 15:
                    total_remaining = sum(len(d) for d in self.history.values())
                    logger.debug(
                        f"🧹 [GC] Aggregator очищен: удалено {total_removed} событий. "
                        f"Осталось в кэше: {total_remaining} по {len(self.history)} тикерам."
                    )

            except Exception as e:
                logger.error(f"❌ Ошибка в cleanup_task агрегатора: {e}", exc_info=True)
                await asyncio.sleep(10)
