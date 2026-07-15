import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from src.database.functions import get_utc_now
from src.database.models import CoinFundamental
from src.utils import normalize_bybit_symbol

logger = logging.getLogger(__name__)


async def sync_coin_fundamentals_list(session: AsyncSession, symbols: list[str]) -> int:
    """Гарантирует наличие всех переданных Bybit-символов в coin_fundamentals."""
    normalized_symbols = sorted(
        {
            normalize_bybit_symbol(symbol).upper()
            for symbol in symbols
            if symbol and normalize_bybit_symbol(symbol)
        }
    )
    if not normalized_symbols:
        return 0

    payload = [
        {
            "symbol": symbol,
            "circulating_supply": 0.0,
            "cg_id": None,
            "last_updated": get_utc_now(),
        }
        for symbol in normalized_symbols
    ]

    stmt = insert(CoinFundamental).values(payload)
    stmt = stmt.on_conflict_do_nothing(index_elements=["symbol"])
    result = await session.execute(stmt)
    await session.commit()

    inserted_count = result.rowcount or 0
    logger.info(
        "Синхронизация списка coin_fundamentals завершена: передано=%s, добавлено=%s.",
        len(normalized_symbols),
        inserted_count,
    )
    return inserted_count
