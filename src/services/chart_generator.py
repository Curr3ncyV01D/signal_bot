import asyncio
import io
import logging
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from typing import TypedDict
from src.core.config import config

logger = logging.getLogger(__name__)


class OhlcRecord(TypedDict):
    t: int
    o: float
    h: float
    l: float
    c: float
    v: float


class ChartCacheEntry(TypedDict):
    file_id: str
    price: float
    ts: float


_chart_executor = ProcessPoolExecutor(max_workers=2)
_chart_cache: dict[str, ChartCacheEntry] = {}
_locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
locks = _locks


def get_cached_id(symbol: str, current_price: float) -> str | None:
    entry = _chart_cache.get(symbol)
    if entry is None:
        return None

    now = time.time()
    if now - entry["ts"] > config.CHART_CACHE_TTL_SEC:
        _chart_cache.pop(symbol, None)
        return None

    last_price = entry["price"]
    if last_price <= 0 or current_price <= 0:
        _chart_cache.pop(symbol, None)
        return None

    price_delta = abs(current_price - last_price) / last_price
    if price_delta >= config.CHART_PRICE_DELTA_THRESHOLD:
        _chart_cache.pop(symbol, None)
        return None

    return entry["file_id"]


def update_cache(symbol: str, file_id: str, price: float) -> None:
    if not file_id or price <= 0:
        return

    _chart_cache[symbol] = {
        "file_id": file_id,
        "price": float(price),
        "ts": time.time(),
    }


def _render_sync(data_list: list[OhlcRecord], symbol: str, alert_title: str) -> bytes:
    import matplotlib

    matplotlib.use("Agg")

    import pandas as pd
    import mplfinance as mpf
    import matplotlib.pyplot as plt

    buffer = io.BytesIO()

    try:
        frame = pd.DataFrame.from_records(data_list)
        if frame.empty:
            raise ValueError("OHLC data is empty")

        frame["t"] = pd.to_datetime(frame["t"], unit="s", utc=True)
        frame = frame.set_index("t")
        frame = frame.rename(
            columns={
                "o": "Open",
                "h": "High",
                "l": "Low",
                "c": "Close",
                "v": "Volume",
            }
        )
        frame = frame[["Open", "High", "Low", "Close", "Volume"]]

        # Расчет отступов для предотвращения перекрытия текстом
        max_price = frame["High"].max()
        min_price = frame["Low"].min()
        price_diff = max_price - min_price if max_price != min_price else 1.0
        
        min_lim = min_price - (price_diff * 0.05)
        max_lim = max_price + (price_diff * 0.20)

        market_colors = mpf.make_marketcolors(
            up="#26a69a",
            down="#ef5350",
            edge="inherit",
            wick="inherit",
            volume="inherit",
        )
        style = mpf.make_mpf_style(
            base_mpf_style="nightclouds",
            marketcolors=market_colors,
            facecolor="#131722",
            figcolor="#131722",
            edgecolor="#131722",
            gridcolor="#2a2e39",
            gridstyle="--",
            y_on_right=True,
            rc={
                "axes.facecolor": "#131722",
                "axes.edgecolor": "#2a2e39",
                "axes.labelcolor": "#d1d4dc",
                "axes.grid": True,
                "figure.facecolor": "#131722",
                "savefig.facecolor": "#131722",
                "text.color": "#d1d4dc",
                "xtick.color": "#787b86",
                "ytick.color": "#d1d4dc",
            },
        )

        fig, axes = mpf.plot(
            frame,
            type="candle",
            style=style,
            volume=True,
            returnfig=True,
            figsize=(10, 5),
            ylim=(min_lim, max_lim),
            tight_layout=True,
            datetime_format="",
            xrotation=0,
            scale_padding={"left": 0.02, "right": 0.06, "top": 0.08, "bottom": 0.02},
            update_width_config={
                "candle_linewidth": 0.8,
                "candle_width": 0.58,
                "volume_width": 0.58,
            },
        )

        fig.text(
            0.02,
            0.95,
            symbol,
            ha="left",
            va="top",
            fontsize=16,
            fontweight="bold",
            color="#d1d4dc",
        )
        fig.text(
            0.98,
            0.95,
            f"{alert_title} | 15m",
            ha="right",
            va="top",
            fontsize=12,
            color="#d1d4dc",
        )

        for axis in axes:
            axis.tick_params(axis="x", which="both", labelbottom=False, bottom=False)
            # Удаляем рамки (spines) для эффекта "безграничности"
            for spine in axis.spines.values():
                spine.set_visible(False)

        fig.savefig(
            buffer,
            format="png",
            dpi=144,
            bbox_inches="tight",
            pad_inches=0.08,
            facecolor=fig.get_facecolor(),
        )
        buffer.seek(0)
        return buffer.getvalue()
    finally:
        buffer.close()
        plt.close("all")


async def get_chart(symbol: str, ohlc_data: list[OhlcRecord], alert_title: str) -> bytes | None:
    if len(ohlc_data) < 2:
        return None

    loop = asyncio.get_running_loop()
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(_chart_executor, _render_sync, ohlc_data, symbol, alert_title),
            timeout=2.5,
        )
    except asyncio.TimeoutError:
        logger.warning(f"Таймаут рендера графика для {symbol}")
        return None
    except Exception as e:
        logger.debug(f"Ошибка генерации графика для {symbol}: {e}")
        return None
