import asyncio
import logging
import aiohttp
import orjson
from datetime import datetime, timezone
from src.core.config import config

logger = logging.getLogger(__name__)

async def fetch_historical_oi(symbol: str, session: aiohttp.ClientSession, semaphore: asyncio.Semaphore, proxy: str | None) -> list[tuple[int, float]]:
    """Скачивает историю OI (раз в 5 мин) для монеты."""
    url = "https://api.bybit.com/v5/market/open-interest"
    params = {
        "category": "linear",
        "symbol": symbol,
        "interval": "5min",
        "limit": 15
    }
    async with semaphore:
        try:
            async with session.get(url, params=params, proxy=proxy) as resp:
                if resp.status == 200:
                    raw_data = await resp.read()
                    data = orjson.loads(raw_data)
                    if data.get("retCode") == 0 and data["result"]["list"]:
                        # [(timestamp_ms, value), ...]
                        return [(int(x["timestamp"]), float(x["openInterest"])) for x in data["result"]["list"]]
        except Exception as e:
            logger.debug(f"Ошибка скачивания OI для {symbol}: {e}")
    return []

async def warmup_system(market_aggregator, target_symbols: list[str]) -> None:
    """
    Принудительный прогрев MarketAggregator перед включением сокетов.
    1. Получает тикеры (ОИ, Цена, Фандинг) за 1 запрос.
    2. Скачивает историю свечей (Kline) и историю OI параллельно.
    """
    logger.info("🚀 Запуск принудительного прогрева ОИ и RSI...")
    
    proxy = config.PROXY_URL if config.PROXY_URL else None
    url_tickers = "https://api.bybit.com/v5/market/tickers"
    params_tickers = {"category": "linear"}
    
    async with aiohttp.ClientSession() as session:
        # 1. ШАГ: Мгновенный прогрев текущих значений
        try:
            async with session.get(url_tickers, params=params_tickers, proxy=proxy) as resp:
                if resp.status == 200:
                    raw_data = await resp.read()
                    res_json = orjson.loads(raw_data)
                    if res_json.get("retCode") == 0:
                        tickers_list = res_json["result"]["list"]
                        for ticker in tickers_list:
                            symbol = ticker["symbol"]
                            if symbol in target_symbols:
                                price = float(ticker.get("lastPrice") or 0)
                                oi = float(ticker.get("openInterestValue") or 0)
                                funding = float(ticker.get("fundingRate") or 0)
                                vol24h = float(ticker.get("turnover24h")) if ticker.get("turnover24h") else None
                                market_aggregator.update(symbol, price, oi, funding, vol24h)
        except Exception as e:
            logger.error(f"Ошибка прогрева тикеров: {e}")

        # 2. ШАГ: Параллельное скачивание Kline и OI History
        url_kline = "https://api.bybit.com/v5/market/kline"
        semaphore = asyncio.Semaphore(20) 
        
        async def fetch_data_for_symbol(symbol: str):
            # Скачиваем свечи (Kline)
            prices = []
            kline_params = {
                "category": "linear",
                "symbol": symbol,
                "interval": config.RSI_KLINE_INTERVAL,
                "limit": 50
            }
            
            # Скачиваем OI и Kline параллельно для одной монеты
            oi_task = fetch_historical_oi(symbol, session, semaphore, proxy)
            
            try:
                async with semaphore:
                    async with session.get(url_kline, params=kline_params, proxy=proxy) as resp:
                        if resp.status == 200:
                            raw_data = await resp.read()
                            data = orjson.loads(raw_data)
                            if data.get("retCode") == 0 and data["result"]["list"]:
                                prices = [float(c[4]) for c in data["result"]["list"]]
                                prices.reverse()
                
                oi_points = await oi_task
                
                if prices:
                    # Наполняем историю MarketAggregator (цены + OI)
                    market_aggregator.seed_history(symbol, prices, oi_points)
                    
                    # Заполняем rsi_prices (для RSI используется Kline)
                    from collections import deque
                    market_aggregator.rsi_prices[symbol] = deque(prices, maxlen=50)
                    
                    now = datetime.now(timezone.utc).timestamp()
                    market_aggregator.rsi_bars[symbol] = int(now // 3600)
            except Exception:
                pass

        logger.info(f"⏳ Скачиваем историю (Kline + OI) по {len(target_symbols)} монетам...")
        tasks = [fetch_data_for_symbol(sym) for sym in target_symbols]
        await asyncio.gather(*tasks)
        logger.info("✅ Прогрев системы завершен.")