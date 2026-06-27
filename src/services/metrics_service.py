import asyncio
import psutil
import time
from datetime import datetime, timezone
from src.core.config import config
from src.database.crud.stats_service import get_financial_metrics, get_audience_metrics
from src.services.bouncer import BouncerManager
from src.services.payment_worker import PaymentManager

class MetricsService:
    _process = None

    @classmethod
    def _get_process(cls):
        if cls._process is None:
            cls._process = psutil.Process()
        return cls._process

    @classmethod
    async def get_system_stats(cls, listener, liq_aggregator, data_queue: asyncio.Queue) -> dict:
        """
        Собирает технические метрики системы (Global Server + Local Process).
        """
        now = datetime.now(timezone.utc)
        process = cls._get_process()
        
        # 1. Uptime
        uptime_delta = now - config.START_TIME if config.START_TIME else None
        uptime_str = str(uptime_delta).split('.')[0] if uptime_delta else "N/A"

        # 2. WebSocket Connections
        total_pool = len(listener.ws_map) if hasattr(listener, 'ws_map') else 0
        active_pool = listener.get_active_connections_count() if hasattr(listener, 'get_active_connections_count') else 0

        # 3. Aggregator Cache
        active_symbols = len(liq_aggregator.history)
        total_events = sum(len(d) for d in liq_aggregator.history.values())

        # 4. Queue Size
        queue_size = data_queue.qsize()

        # 5. Global System Metrics
        server_cpu_pct = await asyncio.to_thread(psutil.cpu_percent, interval=0.1)
        sv_ram = await asyncio.to_thread(psutil.virtual_memory)
        
        # 6. Local Process Metrics
        process_cpu_pct = process.cpu_percent()
        mem_info = process.memory_info()
        process_ram_mb = mem_info.rss / (1024 * 1024)
        process_ram_pct = process.memory_percent()

        return {
            "uptime": uptime_str,
            "active_connections": active_pool,
            "total_connections": total_pool,
            "active_symbols": active_symbols,
            "total_events": total_events,
            "queue_size": queue_size,
            "server_time": now.replace(tzinfo=None).strftime('%H:%M:%S'),

            "server_cpu_pct": server_cpu_pct,
            "server_ram_pct": sv_ram.percent,
            "server_ram_total_gb": sv_ram.total / (1024**3),
            "server_ram_used_gb": sv_ram.used / (1024**3),
            
            "process_cpu_pct": process_cpu_pct,
            "process_ram_mb": process_ram_mb,
            "process_ram_pct": process_ram_pct
        }

    @staticmethod
    def get_analytics_latency(listener) -> str:
        """
        Расчет задержки последнего сигнала.
        """
        if not listener or not hasattr(listener, 'last_message_time') or not listener.last_message_time:
            return "N/A"
            
        now = time.time()
        diff = now - listener.last_message_time
        
        if diff < 1:
            return f"{diff:.2f} сек."
        return f"{int(diff)} сек."

    @staticmethod
    def get_bouncer_status() -> str:
        """
        Возвращает статус последнего прохода Вышибалы.
        """
        if not BouncerManager.last_run:
            return "Ожидание..."
            
        now = datetime.now(timezone.utc)
        diff = (now - BouncerManager.last_run).total_seconds()
        
        if diff < 60:
            return "в эту минуту"
        return f"{int(diff // 60)} мин. назад"

    @staticmethod
    def get_payment_status() -> str:
        """
        Возвращает статус последнего прохода воркера платежей.
        """
        if not PaymentManager.last_run:
            return "ОЖИДАНИЕ..."
            
        now = datetime.now(timezone.utc)
        diff = (now - PaymentManager.last_run).total_seconds()
        if diff < 60:
            return "в эту минуту"
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
        tech_stats["payment_hb"] = cls.get_payment_status()

        # Бизнес метрики (из stats_service)
        financial = await get_financial_metrics(session)
        audience = await get_audience_metrics(session)

        return {
            "tech": tech_stats,
            "financial": financial,
            "audience": audience
        }
