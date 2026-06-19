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

        # Итерируемся по копии ключей, чтобы избежать ошибок при изменении словаря из других потоков
        for symbol, events in list(self.history.items()):
            try:
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

        # Сортируем и берем топ
        top_longs = sorted(longs_map.items(), key=lambda x: x[1], reverse=True)[:limit]
        top_shorts = sorted(shorts_map.items(), key=lambda x: x[1], reverse=True)[:limit]

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

                # 1. Итерируемся по КОПИИ списка ключей (list(...)), 
                # чтобы избежать RuntimeError при удалении ключей из словаря в цикле
                for symbol in list(self.history.keys()):
                    events = self.history[symbol]

                    # 2. Удаляем старые события из начала очереди (пока они старше часа)
                    while events and (now - events[0][0]).total_seconds() > config.WINDOW_VOLUME_1H:
                        events.popleft()
                        total_removed += 1
                    
                    # 3. Если по символу больше нет данных, удаляем сам ключ, 
                    # чтобы не раздувать словарь (Garbage Collection)
                    if not events:
                        del self.history[symbol]
                
                # Логируем результат, только если были удаления
                if total_removed > 15:
                    # Считаем общее кол-во оставшихся событий для мониторинга ОЗУ
                    total_remaining = sum(len(d) for d in self.history.values())
                    logger.debug(
                        f"🧹 [GC] Aggregator очищен: удалено {total_removed} событий. "
                        f"Осталось в кэше: {total_remaining} по {len(self.history)} тикерам."
                    )

            except Exception as e:
                logger.error(f"❌ Ошибка в cleanup_task агрегатора: {e}", exc_info=True)
                await asyncio.sleep(10)
