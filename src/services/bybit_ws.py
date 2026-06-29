import logging
import os
import asyncio
import orjson
import time
from datetime import datetime, timezone

from pybit.unified_trading import WebSocket, HTTP
from src.core.config import config

logger = logging.getLogger(__name__)

class BybitListener:
    def __init__(self, queue: asyncio.Queue, loop: asyncio.AbstractEventLoop):
        self.queue = queue
        self.loop = loop
        self.last_message_time = None
        self.last_heartbeat = {}  # {ws_instance: timestamp}
        self.symbol_statuses = {}  # {symbol: status}
        self._watchdog_task = None
        
        if getattr(config, 'PROXY_URL', None):
            os.environ['HTTP_PROXY'] = config.PROXY_URL
            os.environ['HTTPS_PROXY'] = config.PROXY_URL
            logger.info("Bybit Listener использует прокси")
        
        self.http = HTTP(testnet=False)
        self.ws_map = {}  # {WebSocket: [symbols]}
        self.target_symbols = []
        self._start_count = 0
        self._launch_context = "primary"
        self._ticker_throttle: dict[str, float] = {}

    def get_all_usdt_symbols(self) -> list[str]:
        """Получает список всех активных USDT-пар с Bybit."""
        try:
            resp = self.http.get_instruments_info(category="linear", limit=1000)
            instruments = resp.get("result", {}).get("list", [])
            
            for item in instruments:
                self.symbol_statuses[item["symbol"]] = item["status"]

            symbols = [
                item["symbol"] 
                for item in instruments
                if item["symbol"].endswith("USDT") and item["status"] in ["Trading", "PreLaunch"]
            ]
            logger.debug(f"Найдено {len(symbols)} активных USDT-пар (включая PreLaunch)")
            return symbols
        except Exception as e:
            logger.error(f"Ошибка получения списка символов: {e}")
            return []

    def get_active_connections_count(self):
        active_count = 0
        for ws in self.ws_map.keys():
            try:
                if ws.is_connected():
                    active_count += 1
            except Exception:
                pass
        return active_count

    # --- СПЕЦИАЛИЗИРОВАННЫЕ ОБРАБОТЧИКИ (Фильтрация до очереди) ---

    def on_message(self, message, ws=None):
        """Единая точка входа для всех сообщений WebSocket."""
        self.last_message_time = time.time()

        if ws:
            self.last_heartbeat[ws] = time.monotonic()

        if not isinstance(message, dict):
            try:
                message = orjson.loads(message)
            except Exception:
                return

        # Системные пакеты никогда не должны попадать под throttling.
        if any(key in message for key in ("success", "ret_msg", "op")):
            try:
                is_success = message.get("success")
                req_id = message.get("req_id", "N/A")
                ret_msg = message.get("ret_msg", "")
                op = message.get("op", "")

                if op == "ping" or ret_msg.lower() == "pong":
                    logger.debug("Получен системный ответ Bybit ping/pong")
                elif is_success:
                    logger.debug(f"Подписка подтверждена: {req_id or message.get('conn_id')}")
                elif "success" in message:
                    logger.error(f"Bybit ОТКЛОНИЛ подписку: {ret_msg}. Данные по части монет могут не поступать!")
            except Exception as e:
                logger.error(f"Ошибка при обработке подтверждения подписки: {e}")
            return

        topic = message.get("topic", "")
        if topic.startswith("ticker"):
            symbol = topic.split(".", 1)[1] if "." in topic else ""
            if symbol:
                now_monotonic = time.monotonic()
                throttle_sec = float(getattr(config, "TICKER_THROTTLE_SEC", 2.0))
                last_seen = self._ticker_throttle.get(symbol)
                if last_seen is not None and (now_monotonic - last_seen) < throttle_sec:
                    logger.debug(f"Тикер {symbol} отсечен throttling-шлюзом")
                    return
                self._ticker_throttle[symbol] = now_monotonic
            self.handle_ticker(message)
            return

        topic_lower = topic.lower()
        
        if topic and "liquidation" in topic_lower:
            self.handle_liquidation(message)
        elif topic and "publictrade" in topic_lower:
            self.handle_trade(message)
        elif not topic:
            if "s" in message and "p" in message and "v" in message:
                self.handle_liquidation({"data": message})
        else:
            logger.warning(f"⚠️ Неизвестный топик: {topic}")

    def handle_liquidation(self, message):
        """Обработка ликвидаций (Stage 1)"""
        data = message.get("data")
        
        if not data:
            if "s" in message and "p" in message:
                data = message
            else:
                return
        
        if isinstance(data, list):
            for item in data:
                self.loop.call_soon_threadsafe(self.queue.put_nowait, {"type": "liquidation", "data": item})
        else:
            self.loop.call_soon_threadsafe(self.queue.put_nowait, {"type": "liquidation", "data": data})

    def handle_ticker(self, message):
        """Обработка тикеров: Открытый интерес (OI), Цена, Фандинг"""
        data = message.get("data")
        if not data:
            return
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
            connection_delay = max(config.WS_DELAY_PROD, 2.0)
        
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
                await self.subscribe_to_symbol(ws, symbol)
            
            self.ws_map[ws] = list(chunk)
            
            sys.stdout.write(f"\r📡 Подключение вебсокетов: [{'=' * (i * 20 // len(symbol_chunks)):<20}] {i}/{len(symbol_chunks)}")
            sys.stdout.flush()

            await asyncio.sleep(connection_delay) # Пауза, чтобы не словить бан по IP за спам коннектами

        print() 
        logger.info(f"\n✅ Все {len(self.ws_map)} соединений успешно инициализированы.")
        
        if self._start_count == 0 and not self._watchdog_task:
            self._watchdog_task = asyncio.create_task(self.watchdog_task())

        self._start_count += 1
        self._launch_context = "normal"

    async def watchdog_task(self):
        """Проверка активности сокетов и их реанимация при необходимости."""
        logger.info("📡 Watchdog WebSocket запущен.")
        while True:
            try:
                await asyncio.sleep(60)
                now = time.monotonic()
                
                # Если весь лисенер молчит слишком долго, возможно проблема с сетью вообще
                total_silence = 0
                if self.last_message_time:
                    total_silence = now - self.last_message_time
                
                # Если интернет есть (хотя бы один сокет жив), но конкретный сокет молчит > 3 минут
                for ws, symbols in list(self.ws_map.items()):
                    last_ws_time = self.last_heartbeat.get(ws, 0)
                    silence_duration = now - last_ws_time
                    
                    if silence_duration > 180:
                        # Проверяем, не глобальная ли это тишина (проблема с интернетом)
                        if self.last_message_time is None or total_silence < 180:
                            logger.warning(f"⚠️ Сокет {ws} молчит {int(silence_duration)} сек. Попытка реанимации...")
                            await self.reconnect_chunk(ws)
                        else:
                            logger.debug(f"⏳ Глобальная тишина ({int(total_silence)} сек), Watchdog ожидает восстановления сети.")
            except asyncio.CancelledError:
                logger.info("📡 Watchdog WebSocket остановлен.")
                break
            except Exception as e:
                logger.error(f"Ошибка в watchdog_task: {e}")

    async def reconnect_chunk(self, old_ws):
        """Закрывает старый сокет и создает новый с тем же набором символов."""
        symbols = self.ws_map.get(old_ws, [])
        if not symbols:
            return

        try:
            old_ws.exit()
        except:
            pass
        
        if old_ws in self.ws_map:
            del self.ws_map[old_ws]
        if old_ws in self.last_heartbeat:
            del self.last_heartbeat[old_ws]

        logger.info(f"🔄 Переподключение чанка на {len(symbols)} монет...")
        
        new_ws = WebSocket(
            testnet=False, 
            channel_type="linear",
            ping_interval=20,
            ping_timeout=10,
            restart_on_error=True
        )

        self.ws_map[new_ws] = symbols
        self.last_heartbeat[new_ws] = time.monotonic()

        for symbol in symbols:
            await self.subscribe_to_symbol(new_ws, symbol)
        
        logger.info(f"✅ Чанк успешно пересоздан.")

    def stop(self):
        if self._watchdog_task:
            self._watchdog_task.cancel()
            self._watchdog_task = None

        for ws in self.ws_map.keys():
            try:
                ws.exit()
            except:
                pass
        self.ws_map.clear()
        self.last_heartbeat.clear()
        logger.info("Все WebSocket соединения закрыты.")

    async def subscribe_to_symbol(self, ws, symbol):
        """Подписка на ликвидации, тикеры и сделки для конкретного символа."""
        callback = lambda msg: self.on_message(msg, ws=ws)
        try:
            # ПОДПИСКА 1: Ликвидации
            ws.all_liquidation_stream(symbol=symbol, callback=callback)
            await asyncio.sleep(0.05)
            # ПОДПИСКА 2: Тикеры (OI, Price)
            ws.ticker_stream(symbol=symbol, callback=callback)
            await asyncio.sleep(0.05)
            # ПОДПИСКА 3: Сделки (CVD)
            ws.trade_stream(symbol=symbol, callback=callback)
            await asyncio.sleep(0.05)
        except Exception as e:
            logger.error(f"❌ Ошибка динамической подписки на {symbol}: {e}")

    async def add_new_symbol(self, symbol):
        """Добавление новой монеты без перезагрузки (Hot Swap)."""
        if symbol in self.target_symbols:
            return

        # Ищем существующий сокет с местом
        chunk_size = getattr(config, 'WS_CHUNK_SIZE', 25)
        target_ws = None
        
        for ws, symbols in self.ws_map.items():
            if len(symbols) < chunk_size:
                target_ws = ws
                break
        
        if target_ws:
            await self.subscribe_to_symbol(target_ws, symbol)
            self.ws_map[target_ws].append(symbol)
            logger.info(f"✅ Монета {symbol} добавлена в существующий сокет ({len(self.ws_map[target_ws])}/{chunk_size})")
        else:
            # Создаем новый сокет
            logger.info(f"🚀 Создание нового сокета для {symbol} (все текущие заполнены)")
            ws = WebSocket(
                testnet=False, 
                channel_type="linear",
                ping_interval=20,
                ping_timeout=10,
                restart_on_error=True
            )
            await self.subscribe_to_symbol(ws, symbol)
            self.ws_map[ws] = [symbol]
            
            # Небольшая задержка для стабилизации нового соединения
            await asyncio.sleep(getattr(config, 'WS_DELAY_PROD', 2.0))

        if symbol not in self.target_symbols:
            self.target_symbols.append(symbol)

    def get_detailed_symbol_info(self, symbol: str) -> dict | None:
        """Поиск информации об отслеживаемой монете по всем сокетам."""
        target_symbol = symbol.upper()
        
        for i, (ws, symbols) in enumerate(self.ws_map.items(), 1):
            if target_symbol in [s.upper() for s in symbols]:
                return {
                    "chunk_index": i,
                    "is_connected": ws.is_connected() if hasattr(ws, 'is_connected') else False,
                    "last_heartbeat": self.last_heartbeat.get(ws),
                    "symbols_count": len(symbols),
                    "market_status": self.symbol_statuses.get(target_symbol, "Unknown")
                }
        return None

    def get_all_tracked_grouped(self) -> dict[int, list[str]]:
        """Возвращает список всех монет, сгруппированных по номеру сокета."""
        grouped = {}
        for i, (ws, symbols) in enumerate(self.ws_map.items(), 1):
            grouped[i] = sorted(list(symbols))
        return grouped
