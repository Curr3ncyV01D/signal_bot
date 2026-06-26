import asyncio
import logging
import aiohttp
import orjson
from datetime import datetime, timezone
from sqlalchemy import select
from src.core.config import config
from src.database.models import CoinFundamental
from src.utils import normalize_bybit_symbol, MANUAL_MAPPING

logger = logging.getLogger(__name__)

async def supply_sync_worker(market_aggregator, session_maker):
    """
    Фоновый воркер для синхронизации данных о Circulating Supply с CoinGecko.
    Интервал: 12 часов.
    """
    logger.info("🚀 Воркер синхронизации эмиссии (CoinGecko) запущен.")
    
    while True:
        try:
            # 1. Получаем список всех целевых символов из агрегатора
            # Примечание: предполагается, что в market_aggregator есть доступ к текущим символам
            # Если нет прямого списка, берем ключи из snapshots
            target_symbols = list(market_aggregator.snapshots.keys())
            if not target_symbols:
                logger.debug("Нет символов для синхронизации эмиссии, ждем...")
                await asyncio.sleep(60)
                continue

            logger.info(f"Начинаю синхронизацию эмиссии для {len(target_symbols)} инструментов...")
            
            async with aiohttp.ClientSession() as session:
                proxy = config.PROXY_URL
                
                # ШАГ 1: Получаем полный список монет CoinGecko для маппинга тикеров на ID
                cg_list_url = "https://api.coingecko.com/api/v3/coins/list"
                cg_id_map = {} # {ticker: cg_id}
                
                try:
                    async with session.get(cg_list_url, proxy=proxy, timeout=30) as resp:
                        if resp.status == 200:
                            coins_list = orjson.loads(await resp.read())
                            for coin in coins_list:
                                ticker = coin["symbol"].lower()
                                # Сохраняем первый встреченный ID для тикера (обычно самый релевантный)
                                if ticker not in cg_id_map:
                                    cg_id_map[ticker] = coin["id"]
                        elif resp.status == 429:
                            logger.warning("CoinGecko Rate Limit (429) при получении списка. Ждем 60с...")
                            await asyncio.sleep(60)
                            continue
                        else:
                            logger.error(f"Ошибка CoinGecko API ({resp.status}) при получении списка.")
                            await asyncio.sleep(300)
                            continue
                except Exception as e:
                    logger.error(f"Ошибка запроса к CoinGecko: {e}")
                    await asyncio.sleep(300)
                    continue

                # ШАГ 2: Сопоставляем наши тикеры с CoinGecko ID
                our_mapped_ids = {} # {cg_id: our_clean_symbol}
                for raw_symbol in target_symbols:
                    clean_symbol = normalize_bybit_symbol(raw_symbol)
                    
                    # Проверяем ручной маппинг
                    cg_id = MANUAL_MAPPING.get(clean_symbol.upper())
                    if not cg_id:
                        # Ищем в загруженном списке
                        cg_id = cg_id_map.get(clean_symbol)
                    
                    if cg_id:
                        our_mapped_ids[cg_id] = clean_symbol.upper()
                
                # ШАГ 3: Получаем данные об эмиссии пачками по 250 (лимит API)
                all_cg_ids = list(our_mapped_ids.keys())
                chunk_size = 250
                updated_count = 0
                
                for i in range(0, len(all_cg_ids), chunk_size):
                    chunk = all_cg_ids[i:i + chunk_size]
                    ids_str = ",".join(chunk)
                    markets_url = f"https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids={ids_str}&order=market_cap_desc"
                    
                    try:
                        async with session.get(markets_url, proxy=proxy, timeout=30) as resp:
                            if resp.status == 200:
                                markets_data = orjson.loads(await resp.read())
                                
                                async with session_maker() as db_session:
                                    for coin_data in markets_data:
                                        cg_id = coin_data["id"]
                                        supply = coin_data.get("circulating_supply")
                                        our_symbol = our_mapped_ids.get(cg_id)
                                        
                                        if our_symbol and supply:
                                            # Обновляем в БД
                                            stmt = select(CoinFundamental).where(CoinFundamental.symbol == our_symbol)
                                            result = await db_session.execute(stmt)
                                            db_coin = result.scalar_one_or_none()
                                            
                                            if db_coin:
                                                db_coin.circulating_supply = float(supply)
                                                db_coin.cg_id = cg_id
                                            else:
                                                new_coin = CoinFundamental(
                                                    symbol=our_symbol,
                                                    circulating_supply=float(supply),
                                                    cg_id=cg_id
                                                )
                                                db_session.add(new_coin)
                                            
                                            # Обновляем в агрегаторе (In-Memory)
                                            market_aggregator.update_supply(our_symbol, float(supply))
                                            updated_count += 1
                                            
                                    await db_session.commit()
                            elif resp.status == 429:
                                logger.warning(f"CoinGecko Rate Limit (429) на пачке {i}. Ждем 60с...")
                                await asyncio.sleep(60)
                                # Уменьшаем шаг, чтобы повторить эту же пачку
                                i -= chunk_size
                                continue
                            else:
                                logger.error(f"Ошибка пачки {i}: {resp.status}")
                    except Exception as e:
                        logger.error(f"Критическая ошибка при обработке пачки {i}: {e}")
                    
                    # Небольшая пауза между пачками для вежливости
                    await asyncio.sleep(1)

                logger.info(f"✅ Синхронизация завершена. Успешно обновлено: {updated_count} монет. Пропущено: {len(target_symbols) - updated_count}")

        except Exception as e:
            logger.error(f"Ошибка в supply_sync_worker: {e}", exc_info=True)
        
        # Интервал 12 часов
        await asyncio.sleep(12 * 3600)
