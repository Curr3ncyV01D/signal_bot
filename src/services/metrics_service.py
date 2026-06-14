import asyncio
import psutil
import time
from datetime import datetime, timezone
from src.core.config import config
from src.database.crud.stats_service import get_financial_metrics, get_audience_metrics
from src.services.bouncer import LAST_RUN as BOUNCER_LAST_RUN

class MetricsService:
    @staticmethod
    async def get_system_stats(listener, liq_aggregator, data_queue: asyncio.Queue) -> dict:
        """
        Собирает технические метрики системы.
        """
        now = datetime.now(timezone.utc)
        
        # 1. Uptime
        uptime_delta = now - config.START_TIME if config.START_TIME else None
        uptime_str = str(uptime_delta).split('.')[0] if uptime_delta else "N/A"

        # 2. WebSocket Connections
        total_pool = len(listener.ws_connections) if hasattr(listener, 'ws_connections') else 0
        active_pool = listener.get_active_connections_count() if hasattr(listener, 'get_active_connections_count') else 0

        # 3. Aggregator Cache
        active_symbols = len(liq_aggregator.history)
        total_events = sum(len(d) for d in liq_aggregator.history.values())

        # 4. Queue Size
        queue_size = data_queue.qsize()

        # 5. System Load (CPU/RAM)
        cpu_usage = await asyncio.to_thread(psutil.cpu_percent, interval=0.1)
        ram = await asyncio.to_thread(psutil.virtual_memory)
        ram_usage = ram.percent

        return {
            "uptime": uptime_str,
            "active_connections": active_pool,
            "total_connections": total_pool,
            "active_symbols": active_symbols,
            "total_events": total_events,
            "queue_size": queue_size,
            "cpu_usage": cpu_usage,
            "ram_usage": ram_usage,
            "server_time": now.replace(tzinfo=None).strftime('%H:%M:%S')
        }

    @staticmethod
    def get_analytics_latency(listener) -> str:
        """
        Расчет задержки последнего сигнала.
        """
        if not listener or not hasattr(listener, 'last_message_time') or not listener.last_message_time:
            return "N/A"
            
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        diff = (now - listener.last_message_time).total_seconds()
        
        if diff < 1:
            return f"{diff:.2f} сек."
        return f"{int(diff)} сек."

    @staticmethod
    def get_bouncer_status() -> str:
        """
        Возвращает статус последнего прохода Вышибалы.
        """
        if not BOUNCER_LAST_RUN:
            return "Ожидание..."
            
        now = datetime.now(timezone.utc)
        diff = (now - BOUNCER_LAST_RUN).total_seconds()
        
        if diff < 60:
            return "Только что"
        return f"{int(diff // 60)} мин. назад"

    @classmethod
    async def get_admin_bi_data(cls, session, listener, liq_aggregator, data_queue: asyncio.Queue) -> dict:
        """
        Объединяет технические и бизнес-метрики для админ-панели.
        """
        # Технические метрики
        tech_stats = await cls.get_system_stats(listener, liq_aggregator, data_queue)
        tech_stats["latency"] = cls.get_analytics_latency(listener)
        tech_stats["bouncer_hb"] = cls.get_bouncer_status()

        # Бизнес метрики (из stats_service)
        financial = await get_financial_metrics(session)
        audience = await get_audience_metrics(session)

        return {
            "tech": tech_stats,
            "financial": financial,
            "audience": audience
        }
