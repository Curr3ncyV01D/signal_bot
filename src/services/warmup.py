import asyncio
import logging
import aiohttp
from datetime import datetime, timezone
from src.core.config import config

logger = logging.getLogger(__name__)

async def warmup_system(market_aggregator, target_symbols: list[str]) -> None:
    """
    Принудительный прогрев MarketAggregator перед включением сокетов.
    1. Получает тикеры (ОИ, Цена, Фандинг) для ВСЕХ монет за 1 запрос.
    2. Скачивает историю последних 30 свечей для мгновенного расчета RSI.
    """
    logger.info("🚀 Запуск принудительного прогрева ОИ и RSI...")
    
    proxy = config.PROXY_URL if config.PROXY_URL else None
    url_tickers = "https://api.bybit.com/v5/market/tickers"
    params_tickers = {"category": "linear"}
    
    # 1. ШАГ: Мгновенный прогрев ОИ, Цены и Фандинга
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url_tickers, params=params_tickers, proxy=proxy) as resp:
                if resp.status == 200:
                    res_json = await resp.json()
                    if res_json.get("retCode") == 0:
                        tickers_list = res_json["result"]["list"]
                        count_tickers = 0
                        for ticker in tickers_list:
                            symbol = ticker["symbol"]
                            if symbol in target_symbols:
                                price = float(ticker.get("lastPrice") or 0)
                                oi = float(ticker.get("openInterestValue") or 0)
                                funding = float(ticker.get("fundingRate") or 0)
                                
                                # Заполняем snapshots напрямую
                                market_aggregator.update(symbol, price, oi, funding)
                                count_tickers += 1
                        logger.info(f"✅ Успешно прогрето {count_tickers} тикеров в ОЗУ.")
        except Exception as e:
            logger.error(f"Ошибка прогрева тикеров: {e}")

        # 2. ШАГ: Прогрев истории цен для RSI (Потоками с контролем лимитов)
        url_kline = "https://api.bybit.com/v5/market/kline"
        # Ограничиваем до 10 параллельных запросов, чтобы Bybit не забанил прокси
        semaphore = asyncio.Semaphore(10) 
        
        async def fetch_single_kline(symbol: str):
            async with semaphore:
                params = {
                    "category": "linear",
                    "symbol": symbol,
                    "interval": config.RSI_KLINE_INTERVAL,
                    "limit": 50
                }
                try:
                    async with session.get(url_kline, params=params, proxy=proxy) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data.get("retCode") == 0 and data["result"]["list"]:
                                # Вытаскиваем цены закрытия
                                prices = [float(c[4]) for c in data["result"]["list"]]
                                prices.reverse() # Нам нужна хронология
                                
                                # Заполняем rsi_prices в агрегаторе напрямую
                                from collections import deque
                                market_aggregator.rsi_prices[symbol] = deque(prices, maxlen=50)
                                # Фиксируем ID текущего бара
                                now = datetime.now(timezone.utc).timestamp()
                                # Часовой бар для RSI 1H
                                market_aggregator.rsi_bars[symbol] = int(now // 3600)
                except Exception:
                    pass # Игнорируем точечные сбои сети

        logger.info(f"⏳ Скачиваем историю свечей для RSI по {len(target_symbols)} монетам...")
        tasks = [fetch_single_kline(sym) for sym in target_symbols]
        await asyncio.gather(*tasks)
        logger.info("✅ История цен для RSI успешно загружена в память.")