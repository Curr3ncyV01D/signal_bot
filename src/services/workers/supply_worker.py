import asyncio
import logging
from collections import defaultdict

import aiohttp
import orjson
from sqlalchemy import case, select, update
from sqlalchemy.dialects.postgresql import insert

from src.core.config import config
from src.database.functions import get_utc_now
from src.database.models import CoinFundamental, CoinMapping
from src.database.session import async_session
from src.utils import normalize_bybit_symbol

logger = logging.getLogger(__name__)


COINGECKO_COINS_LIST_URL = "https://api.coingecko.com/api/v3/coins/list"
COINGECKO_MARKETS_URL = "https://api.coingecko.com/api/v3/coins/markets"
COINGECKO_TOP_MARKETS_PARAMS = {
    "vs_currency": "usd",
    "order": "market_cap_desc",
    "per_page": 250,
    "page": 1,
    "sparkline": "false",
}
SYNC_INTERVAL_SECONDS = 12 * 3600
RATE_LIMIT_BACKOFF_BASE_SECONDS = 30
RATE_LIMIT_BACKOFF_MAX_SECONDS = 15 * 60
RETRY_ON_ERROR_SECONDS = 300
CHUNK_SIZE = 250


async def _load_target_symbols() -> list[str]:
    """Берет список монет напрямую из БД"""
    async with async_session() as db_session:
        result = await db_session.execute(
            select(CoinFundamental.symbol).distinct().order_by(CoinFundamental.symbol)
        )
        return list(result.scalars().all())


async def _load_manual_overrides() -> dict[str, str]:
    """Читает ручные переопределения тикеров из БД."""
    async with async_session() as db_session:
        result = await db_session.execute(select(CoinMapping.symbol, CoinMapping.cg_id))
        return {
            normalize_bybit_symbol(symbol).upper(): cg_id
            for symbol, cg_id in result.all()
        }


async def _fetch_json(
    session: aiohttp.ClientSession,
    url: str,
    *,
    proxy: str | None,
    request_name: str,
    params: dict[str, str | int] | None = None,
    rate_limit_attempts: dict[str, int] | None = None,
) -> tuple[object | None, int | None]:
    """Возвращает JSON-ответ и рекомендованную задержку перед повтором при ошибке."""
    try:
        async with session.get(url, params=params, proxy=proxy, timeout=30) as resp:
            if resp.status == 200:
                if rate_limit_attempts is not None:
                    rate_limit_attempts.pop(request_name, None)
                return orjson.loads(await resp.read()), None

            if resp.status == 429:
                attempt = 1
                if rate_limit_attempts is not None:
                    attempt = rate_limit_attempts.get(request_name, 0) + 1
                    rate_limit_attempts[request_name] = attempt
                retry_delay = min(
                    RATE_LIMIT_BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)),
                    RATE_LIMIT_BACKOFF_MAX_SECONDS,
                )
                logger.warning(
                    "CoinGecko Rate Limit (429) при запросе %s. Backoff attempt=%s, повтор через %sс.",
                    request_name,
                    attempt,
                    retry_delay,
                )
                return None, retry_delay

            if rate_limit_attempts is not None:
                rate_limit_attempts.pop(request_name, None)
            logger.error("Ошибка CoinGecko API (%s) при запросе %s.", resp.status, request_name)
            return None, RETRY_ON_ERROR_SECONDS
    except Exception as exc:
        if rate_limit_attempts is not None:
            rate_limit_attempts.pop(request_name, None)
        logger.error("Ошибка запроса CoinGecko (%s): %s", request_name, exc)
        return None, RETRY_ON_ERROR_SECONDS


def _build_symbol_id_map(coins: list[dict], *, request_name: str) -> dict[str, str]:
    """Строит map symbol -> cg_id, сохраняя первый по приоритету элемент."""
    cg_id_map: dict[str, str] = {}

    for coin in coins:
        cg_id = coin.get("id")
        symbol = coin.get("symbol")
        if not cg_id or not symbol:
            continue

        clean_symbol = normalize_bybit_symbol(symbol).upper()
        if clean_symbol not in cg_id_map:
            cg_id_map[clean_symbol] = cg_id

    logger.info("Подготовлен %s map: %s уникальных символов.", request_name, len(cg_id_map))
    return cg_id_map


def _resolve_symbol_ids(
    target_symbols: list[str],
    manual_overrides: dict[str, str],
    top_market_map: dict[str, str],
    fallback_map: dict[str, str],
) -> tuple[dict[str, str], list[str], dict[str, int]]:
    """Иерархия резолва: manual override -> top market cap -> coins/list fallback."""
    resolved_by_symbol: dict[str, str] = {}
    unresolved_symbols: list[str] = []
    resolution_stats = {
        "manual": 0,
        "top_market": 0,
        "fallback": 0,
    }

    for raw_symbol in target_symbols:
        symbol = normalize_bybit_symbol(raw_symbol).upper()
        cg_id = manual_overrides.get(symbol)

        if cg_id:
            resolution_stats["manual"] += 1
        else:
            cg_id = top_market_map.get(symbol)
            if cg_id:
                resolution_stats["top_market"] += 1
            else:
                cg_id = fallback_map.get(symbol)
                if cg_id:
                    resolution_stats["fallback"] += 1

        if not cg_id:
            unresolved_symbols.append(symbol)
            continue

        resolved_by_symbol[symbol] = cg_id

    return resolved_by_symbol, unresolved_symbols, resolution_stats


async def _upsert_fundamentals(payload: list[dict[str, object]]) -> None:
    if not payload:
        return

    async with async_session() as db_session:
        stmt = insert(CoinFundamental).values(payload)
        stmt = stmt.on_conflict_do_update(
            index_elements=["symbol"],
            set_={
                "circulating_supply": stmt.excluded.circulating_supply,
                "cg_id": stmt.excluded.cg_id,
                "last_updated": stmt.excluded.last_updated,
            },
        )
        await db_session.execute(stmt)
        await db_session.commit()


async def _sync_resolved_cg_ids(resolved_by_symbol: dict[str, str]) -> int:
    """Фиксирует итоговый cg_id в БД сразу после резолва, даже если supply еще не обновился."""
    if not resolved_by_symbol:
        return 0

    symbols = list(resolved_by_symbol.keys())
    async with async_session() as db_session:
        current_rows = await db_session.execute(
            select(CoinFundamental.symbol, CoinFundamental.cg_id).where(CoinFundamental.symbol.in_(symbols))
        )
        current_map = dict(current_rows.all())

        changed_symbols = [
            symbol
            for symbol, resolved_cg_id in resolved_by_symbol.items()
            if current_map.get(symbol) != resolved_cg_id
        ]
        if not changed_symbols:
            return 0

        resolved_case = case(
            {symbol: resolved_by_symbol[symbol] for symbol in changed_symbols},
            value=CoinFundamental.symbol,
        )
        stmt = (
            update(CoinFundamental)
            .where(CoinFundamental.symbol.in_(changed_symbols))
            .values(
                cg_id=resolved_case,
                last_updated=get_utc_now(),
            )
        )
        await db_session.execute(stmt)
        await db_session.commit()
        return len(changed_symbols)


def _log_unresolved_symbols(unresolved_symbols: list[str]) -> None:
    """Логирует символы, для которых не удалось подобрать CoinGecko ID."""
    if not unresolved_symbols:
        return

    logger.warning(
        "[MCAP] Не найден маппинг для: %s. Добавьте их в таблицу coin_mapping.",
        ", ".join(sorted(set(unresolved_symbols))),
    )


async def supply_sync_worker(market_aggregator):
    """
    Фоновый воркер для синхронизации данных о Circulating Supply с CoinGecko.
    Интервал: 12 часов.
    """
    logger.info("🚀 Воркер синхронизации эмиссии (CoinGecko) запущен.")

    while True:
        try:
            target_symbols = await _load_target_symbols()
            if not target_symbols:
                logger.debug("В `coin_fundamentals` пока нет символов для синхронизации эмиссии, ждем...")
                await asyncio.sleep(60)
                continue

            logger.info(f"Начинаю синхронизацию эмиссии для {len(target_symbols)} инструментов...")

            async with aiohttp.ClientSession() as session:
                proxy = config.PROXY_URL
                rate_limit_attempts: dict[str, int] = {}

                manual_overrides = await _load_manual_overrides()

                top_markets_data, retry_delay = await _fetch_json(
                    session,
                    COINGECKO_MARKETS_URL,
                    proxy=proxy,
                    request_name="top-250 markets",
                    params=COINGECKO_TOP_MARKETS_PARAMS,
                    rate_limit_attempts=rate_limit_attempts,
                )
                if top_markets_data is None:
                    await asyncio.sleep(retry_delay or RETRY_ON_ERROR_SECONDS)
                    continue

                coins_list_data, retry_delay = await _fetch_json(
                    session,
                    COINGECKO_COINS_LIST_URL,
                    proxy=proxy,
                    request_name="coins/list",
                    rate_limit_attempts=rate_limit_attempts,
                )
                if coins_list_data is None:
                    await asyncio.sleep(retry_delay or RETRY_ON_ERROR_SECONDS)
                    continue

                top_market_map = _build_symbol_id_map(top_markets_data, request_name="top-250")
                fallback_map = _build_symbol_id_map(coins_list_data, request_name="coins/list")
                resolved_by_symbol, unresolved_symbols, resolution_stats = _resolve_symbol_ids(
                    target_symbols=target_symbols,
                    manual_overrides=manual_overrides,
                    top_market_map=top_market_map,
                    fallback_map=fallback_map,
                )

                if not resolved_by_symbol:
                    logger.warning("Не удалось сопоставить CoinGecko ID ни для одного символа из БД.")
                    _log_unresolved_symbols(unresolved_symbols)
                    await asyncio.sleep(SYNC_INTERVAL_SECONDS)
                    continue

                logger.info(
                    "Итог резолва cg_id: manual=%s, top_market=%s, fallback=%s, unresolved=%s.",
                    resolution_stats["manual"],
                    resolution_stats["top_market"],
                    resolution_stats["fallback"],
                    len(unresolved_symbols),
                )
                synced_cg_ids = await _sync_resolved_cg_ids(resolved_by_symbol)
                if synced_cg_ids:
                    logger.info("Синхронизированы итоговые cg_id в БД для %s символов.", synced_cg_ids)

                cg_id_to_symbols: dict[str, list[str]] = defaultdict(list)
                for symbol, cg_id in resolved_by_symbol.items():
                    cg_id_to_symbols[cg_id].append(symbol)

                all_cg_ids = list(cg_id_to_symbols.keys())
                updated_symbols: set[str] = set()
                chunk_index = 0

                while chunk_index < len(all_cg_ids):
                    chunk = all_cg_ids[chunk_index:chunk_index + CHUNK_SIZE]
                    markets_data, retry_delay = await _fetch_json(
                        session,
                        COINGECKO_MARKETS_URL,
                        proxy=proxy,
                        request_name=f"supply chunk {chunk_index // CHUNK_SIZE + 1}",
                        params={
                            "vs_currency": "usd",
                            "ids": ",".join(chunk),
                            "order": "market_cap_desc",
                            "per_page": len(chunk),
                            "page": 1,
                            "sparkline": "false",
                        },
                        rate_limit_attempts=rate_limit_attempts,
                    )
                    if markets_data is None:
                        await asyncio.sleep(retry_delay or RETRY_ON_ERROR_SECONDS)
                        continue

                    upsert_payload: list[dict[str, object]] = []
                    for coin_data in markets_data:
                        cg_id = coin_data.get("id")
                        supply = coin_data.get("circulating_supply")
                        if not cg_id or supply is None:
                            continue

                        supply_val = float(supply)
                        for symbol in cg_id_to_symbols.get(cg_id, []):
                            upsert_payload.append(
                                {
                                    "symbol": symbol,
                                    "circulating_supply": supply_val,
                                    "cg_id": cg_id,
                                    "last_updated": get_utc_now(),
                                }
                            )
                            market_aggregator.update_supply(symbol, supply_val)
                            updated_symbols.add(symbol)

                    await _upsert_fundamentals(upsert_payload)
                    chunk_index += CHUNK_SIZE

                    # Небольшая пауза между пачками для вежливости.
                    await asyncio.sleep(1)

                logger.info(
                    "✅ Синхронизация завершена. Обновлено: %s. Без supply: %s. Без cg_id: %s",
                    len(updated_symbols),
                    len(resolved_by_symbol) - len(updated_symbols),
                    len(unresolved_symbols),
                )
                _log_unresolved_symbols(unresolved_symbols)

        except Exception as exc:
            logger.error(f"Ошибка в supply_sync_worker: {exc}", exc_info=True)
            await asyncio.sleep(1)
            continue

        await asyncio.sleep(SYNC_INTERVAL_SECONDS)
