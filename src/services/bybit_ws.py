import logging
import os
import asyncio
from pybit.unified_trading import WebSocket, HTTP
from src.core.config import config

logger = logging.getLogger(__name__)

class BybitListener:
    def __init__(self, queue: asyncio.Queue, loop: asyncio.AbstractEventLoop):
        self.queue = queue
        self.loop = loop
        
        if config.PROXY_URL:
            os.environ['HTTP_PROXY'] = config.PROXY_URL
            os.environ['HTTPS_PROXY'] = config.PROXY_URL
            logger.info("Bybit Listener использует прокси")
        
        self.http = HTTP(testnet=False)
        # Список для хранения всех открытых вебсокетов
        self.ws_connections = []

    def get_all_usdt_symbols(self):
        """Получает список всех актуальных USDT-пар"""
        try:
            response = self.http.get_instruments_info(category="linear", status="Trading")
            return [
                item['symbol'] for item in response['result']['list'] 
                if item['symbol'].endswith('USDT')
            ]
        except Exception as e:
            logger.error(f"Ошибка получения тикеров: {e}")
            return ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

    def handle_message(self, message):
        """Общий обработчик для всех соединений"""
        if "data" not in message:
            return
        data = message.get("data")
        
        if isinstance(data, list):
            for item in data:
                self.loop.call_soon_threadsafe(self.queue.put_nowait, item)
        else:
            self.loop.call_soon_threadsafe(self.queue.put_nowait, data)

    def start(self):
        import sys

        all_symbols = self.get_all_usdt_symbols()
        ignored_set = set(config.IGNORED_SYMBOLS)
        
        # Фильтруем монеты
        target_symbols = [s for s in all_symbols if s not in ignored_set]
        
        chunk_size = 10
        symbol_chunks = [target_symbols[i:i + chunk_size] for i in range(0, len(target_symbols), chunk_size)]
        
        logger.info(f"Запуск мониторинга. Всего монет: {len(target_symbols)}. Соединений: {len(symbol_chunks)}")

        for i, chunk in enumerate(symbol_chunks, 1):
            ws = WebSocket(testnet=False, channel_type="linear")
            for symbol in chunk:
                try:
                    ws.all_liquidation_stream(symbol=symbol, callback=self.handle_message)
                except Exception as e:
                    logger.error(f"Ошибка подписки на {symbol}: {e}")
            
            self.ws_connections.append(ws)
            
            sys.stdout.write(f"\r📡 Подключение вебсокетов: [{'=' * (i * 20 // len(symbol_chunks)):<20}] {i}/{len(symbol_chunks)}")
            sys.stdout.flush()

            import time
            time.sleep(0.3)

        print() # Перенос каретки на новую строку после прогресс бара
        logger.info(f"\n✅ Все {len(self.ws_connections)} соединений успешно инициализированы.")
        
        logger.info(
            f"BybitListener запущен: подписались на {len(target_symbols)} пар. "
            f"Пропущено (blacklist): {len(all_symbols) - len(target_symbols)}"
        )

    def stop(self):
        """Метод для корректной остановки всех соединений"""
        for ws in self.ws_connections:
            try:
                ws.exit()
            except:
                pass
        logger.info("Все WebSocket соединения закрыты.")

bybit_listener: 'BybitListener' = None


# Инициализируем в main.py