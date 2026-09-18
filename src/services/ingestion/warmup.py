import asyncio
import logging
import aiohttp
import orjson
import time
from collections import deque
from src.core.config import config

logger = logging.getLogger(__name__)


def _parse_float(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


async def fetch_kline(
    symbol: str,
    interval: str,
    limit: int,
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    proxy: str | None,
) -> list[list[str]]:
    """Скачивает Kline и возвращает список баров в хронологическом порядке."""
    url = "https://api.bybit.com/v5/market/kline"
    params = {
        "category": "linear",
        "symbol": symbol,
        "interval": interval,
        "limit": limit,
    }

    async with semaphore:
        try:
            async with session.get(url, params=params, proxy=proxy) as resp:
                if resp.status != 200:
                    return []

                raw_data = await resp.read()
                data = orjson.loads(raw_data)
                if data.get("retCode") != 0:
                    return []

                kline_rows = data.get("result", {}).get("list") or []
                kline_rows.reverse()
                return kline_rows
        except Exception as e:
            logger.debug(f"Ошибка скачивания Kline для {symbol} [{interval}]: {e}")
            return []

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


async def warmup_ohlc(
    market_aggregator,
    target_symbols: list[str],
    session: aiohttp.ClientSession | None = None,
) -> None:
    """Прогрев 15-минутных OHLCV свечей для графиков."""
    if not target_symbols:
        return

    proxy = config.PROXY_URL if config.PROXY_URL else None
    semaphore = asyncio.Semaphore(20)
    own_session = session is None
    active_session = session or aiohttp.ClientSession()

    try:
        logger.info(f"📈 Прогрев 15m OHLCV по {len(target_symbols)} монетам...")

        async def fetch_symbol_ohlc(symbol: str) -> None:
            rows = await fetch_kline(symbol, "15", 100, active_session, semaphore, proxy)
            if not rows:
                return

            candles: list[dict[str, int | float]] = []
            for row in rows:
                if len(row) < 7:
                    continue

                try:
                    candles.append({
                        "t": int(int(row[0]) // 1000),
                        "o": float(row[1]),
                        "h": float(row[2]),
                        "l": float(row[3]),
                        "c": float(row[4]),
                        "v": float(row[6]),
                    })
                except (TypeError, ValueError):
                    continue

            if candles:
                market_aggregator.seed_ohlc_history(symbol, candles)

        await asyncio.gather(*(fetch_symbol_ohlc(symbol) for symbol in target_symbols))
    finally:
        if own_session:
            await active_session.close()

async def warmup_system(market_aggregator, target_symbols: list[str]) -> None:
    """
    Принудительный прогрев MarketAggregator перед включением сокетов.
    1. Получает тикеры (ОИ, Цена, Фандинг) за 1 запрос.
    2. Скачивает историю свечей (Kline) и историю OI параллельно.
    """
    logger.info("🚀 Запуск принудительного прогрева рынка...")
    
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
                                price = _parse_float(ticker.get("lastPrice")) or 0.0
                                oi = _parse_float(ticker.get("openInterestValue")) or 0.0
                                funding = _parse_float(ticker.get("fundingRate")) or 0.0
                                vol24h = _parse_float(ticker.get("turnover24h"))
                                market_aggregator.update(symbol, price, oi, funding, vol24h)
        except Exception as e:
            logger.error(f"Ошибка прогрева тикеров: {e}")

        # 2. ШАГ: Параллельное скачивание Hourly Kline для RSI и OI History
        semaphore = asyncio.Semaphore(20)
        
        async def fetch_rsi_and_oi(symbol: str) -> None:
            try:
                rsi_rows, oi_points = await asyncio.gather(
                    fetch_kline(symbol, config.RSI_KLINE_INTERVAL, 50, session, semaphore, proxy),
                    fetch_historical_oi(symbol, session, semaphore, proxy),
                )

                prices = [float(row[4]) for row in rsi_rows if len(row) >= 5]
                if prices:
                    market_aggregator.seed_history(symbol, prices, oi_points)
                    market_aggregator.rsi_prices[symbol] = deque(prices, maxlen=50)
                    market_aggregator.rsi_bars[symbol] = int(time.time() // 3600)
            except Exception as e:
                logger.debug(f"Ошибка прогрева OI/RSI для {symbol}: {e}")

        logger.info(f"⏳ Скачиваем историю OI/RSI по {len(target_symbols)} монетам...")
        await asyncio.gather(*(fetch_rsi_and_oi(symbol) for symbol in target_symbols))

        logger.info("✅ Прогрев системы завершен.")
