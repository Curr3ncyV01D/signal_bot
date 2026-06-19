import logging
import os
import asyncio
import orjson
from datetime import datetime, timezone

from pybit.unified_trading import WebSocket, HTTP
from src.core.config import config

logger = logging.getLogger(__name__)

class BybitListener:
    def __init__(self, queue: asyncio.Queue, loop: asyncio.AbstractEventLoop):
        self.queue = queue
        self.loop = loop
        self.last_message_time = None
        
        if getattr(config, 'PROXY_URL', None):
            os.environ['HTTP_PROXY'] = config.PROXY_URL
            os.environ['HTTPS_PROXY'] = config.PROXY_URL
            logger.info("Bybit Listener использует прокси")
        
        self.http = HTTP(testnet=False)
        self.ws_connections = []
        self.target_symbols = []
        self._start_count = 0
        self._launch_context = "primary"

    def get_all_usdt_symbols(self) -> list[str]:
        """Получает список всех активных USDT-пар с Bybit."""
        try:
            resp = self.http.get_instruments_info(category="linear")
            symbols = [
                item["symbol"] 
                for item in resp.get("result", {}).get("list", []) 
                if item["symbol"].endswith("USDT") and item["status"] == "Trading"
            ]
            return symbols
        except Exception as e:
            logger.error(f"Ошибка получения списка символов: {e}")
            return []

    def get_active_connections_count(self):
        active_count = 0
        for ws in self.ws_connections:
            try:
                if ws.is_connected():
                    active_count += 1
            except Exception as e:
                pass
        return active_count

    # --- СПЕЦИАЛИЗИРОВАННЫЕ ОБРАБОТЧИКИ (Фильтрация до очереди) ---

    def on_message(self, message):
        """Единая точка входа для всех сообщений WebSocket."""
        # Если пришел словарь (от pybit), мы не можем использовать orjson.loads
        if not isinstance(message, dict):
            try:
                message = orjson.loads(message)
            except Exception:
                return

        topic = message.get("topic", "")
        if not topic: return

        if "liquidation" in topic:
            self.handle_liquidation(message)
        elif "ticker" in topic:
            self.handle_ticker(message)
        elif "publicTrade" in topic:
            self.handle_trade(message)

    def handle_liquidation(self, message):
        """Обработка ликвидаций (Stage 1)"""
        data = message.get("data")
        if not data: return
        
        self.last_message_time = datetime.now(timezone.utc).replace(tzinfo=None)
        
        # Оборачиваем в type: liquidation, чтобы Воркер понял
        if isinstance(data, list):
            for item in data:
                self.loop.call_soon_threadsafe(self.queue.put_nowait, {"type": "liquidation", "data": item})
        else:
            self.loop.call_soon_threadsafe(self.queue.put_nowait, {"type": "liquidation", "data": data})

    def handle_ticker(self, message):
        """Обработка тикеров: Открытый интерес (OI), Цена, Фандинг"""
        data = message.get("data")
        if not data: return
        
        self.last_message_time = datetime.now(timezone.utc).replace(tzinfo=None)
        topic = message.get("topic", "")
        
        # Оборачиваем в type: ticker
        self.loop.call_soon_threadsafe(self.queue.put_nowait, {"type": "ticker", "topic": topic, "data": data})

    def handle_trade(self, message):
        """Обработка публичных сделок (CVD)"""
        data = message.get("data")
        if not data: return

        limit = config.MIN_TRADE_VALUE_FOR_CVD
        filtered = [
            t for t in data 
            if (p := float(t['p'])) * (v := float(t['v'])) >= limit
        ]
        
        if not filtered: return

        self.last_message_time = datetime.now(timezone.utc).replace(tzinfo=None)
        topic = message.get("topic", "")
        self.loop.call_soon_threadsafe(self.queue.put_nowait, {"type": "trade", "topic": topic, "data": filtered})

    # -------------------------------------------------------------

    async def start(self):
        import sys

        # Если монеты уже прогреты и прокинуты из main.py — используем их 
        if self.target_symbols:
            target_symbols = list(self.target_symbols)
        else:
            all_symbols = self.get_all_usdt_symbols()
            ignored_set = set(getattr(config, 'IGNORED_SYMBOLS', []))
            target_symbols = [s for s in all_symbols if s not in ignored_set]
            
            if config.DEV_MODE:
                target_symbols = target_symbols[:config.DEV_SYMBOL_LIMIT]
                logger.warning(f"🚧 DEV MODE: Мониторинг ограничен до {len(target_symbols)} пар.")

        # ПРИНУДИТЕЛЬНО добавляем BTCUSDT
        if "BTCUSDT" not in target_symbols:
            target_symbols.append("BTCUSDT")
        self.target_symbols = target_symbols

        # --- ЛОГИКА ЗАДЕРЖКИ ---
        if config.DEV_MODE:
            connection_delay = config.WS_DELAY_DEV 
        else:
            connection_delay = config.WS_DELAY_PROD
        
        chunk_size = getattr(config, 'WS_CHUNK_SIZE', 25)
        symbol_chunks = [target_symbols[i:i + chunk_size] for i in range(0, len(target_symbols), chunk_size)]

        if self._start_count == 0:
            logger.info(f"Первичный запуск мониторинга. Всего монет: {len(target_symbols)}. Соединений: {len(symbol_chunks)}")
        elif self._launch_context == "listing_restart":
            logger.info(f"Перезапуск мониторинга по листингу. Всего монет: {len(target_symbols)}. Соединений: {len(symbol_chunks)}")
        else:
            logger.info(f"Повторный запуск мониторинга. Всего монет: {len(target_symbols)}. Соединений: {len(symbol_chunks)}")

        for i, chunk in enumerate(symbol_chunks, 1):
            ws = WebSocket(
                testnet=False, 
                channel_type="linear",
                ping_interval=20,
                ping_timeout=10,
                restart_on_error=True
            )
            
            for symbol in chunk:
                try:
                    # ПОДПИСКА 1: Ликвидации
                    ws.all_liquidation_stream(symbol=symbol, callback=self.on_message)
                    # ПОДПИСКА 2: Тикеры (OI, Price)
                    ws.ticker_stream(symbol=symbol, callback=self.on_message)
                    # ПОДПИСКА 3: Сделки (CVD)
                    ws.trade_stream(symbol=symbol, callback=self.on_message)
                except Exception as e:
                    logger.error(f"Ошибка подписки на {symbol}: {e}")
            
            self.ws_connections.append(ws)
            
            sys.stdout.write(f"\r📡 Подключение вебсокетов: [{'=' * (i * 20 // len(symbol_chunks)):<20}] {i}/{len(symbol_chunks)}")
            sys.stdout.flush()

            await asyncio.sleep(connection_delay) # Пауза, чтобы не словить бан по IP за спам коннектами

        print() 
        logger.info(f"\n✅ Все {len(self.ws_connections)} соединений успешно инициализированы.")
        self._start_count += 1
        self._launch_context = "normal"

    async def restart(self, new_symbols: list[str]):
        logger.info("Обновление списка символов: выполняется перезапуск WebSocket-подключений.")
        self.stop()
        self.target_symbols = list(new_symbols)
        self._launch_context = "listing_restart"
        await self.start()

    def stop(self):
        for ws in self.ws_connections:
            try:
                ws.exit()
            except:
                pass
        self.ws_connections.clear()
        logger.info("Все WebSocket соединения закрыты.")
