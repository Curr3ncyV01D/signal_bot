import asyncio
import logging
from collections import deque
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

class UserStatsManager:
    def __init__(self):
        # Личная статистика: { user_id: deque([ts1, ts2, ...]) }
        self._user_signals = {}

    def _get_now(self):
        """Вспомогательный метод для получения единого времени UTC"""
        return datetime.now(timezone.utc).replace(tzinfo=None)

    def add_signal(self, user_id: int):
        """Фиксирует факт отправки сигнала пользователю"""
        now = self._get_now()
        
        # Добавляем в личную историю пользователя
        if user_id not in self._user_signals:
            self._user_signals[user_id] = deque()
        self._user_signals[user_id].append(now)
        
        # Очищаем "старые" записи сразу при добавлении
        self._cleanup_user(user_id)

    def get_count_24h(self, user_id: int) -> int:
        """Возвращает количество сигналов пользователя за 24ч"""
        self._cleanup_user(user_id)
        return len(self._user_signals.get(user_id, []))

    def _cleanup_user(self, user_id: int):
        """Удаляет метки старше 24 часов для пользователя"""
        if user_id not in self._user_signals:
            return
        
        threshold = self._get_now() - timedelta(hours=24)
        history = self._user_signals[user_id]
        
        while history and history[0] < threshold:
            history.popleft()

    async def global_cleanup_task(self):
        """Фоновая задача: полная очистка памяти (раз в час)"""
        while True:
            await asyncio.sleep(3600)
            try:
                # Удаляем совсем неактивных юзеров, чтобы словарь не рос вечно
                for user_id in list(self._user_signals.keys()):
                    self._cleanup_user(user_id)
                    if not self._user_signals[user_id]:
                        del self._user_signals[user_id]
                
                logger.info("Плановая очистка статистики выполнена.")
            except Exception as e:
                logger.error(f"Ошибка при фоновой очистке статистики: {e}")

stats_manager = UserStatsManager()