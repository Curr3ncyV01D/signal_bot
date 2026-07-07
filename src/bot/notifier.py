import asyncio
import logging
import re
from aiogram import Bot
from aiogram.utils.markdown import hbold, hlink
from aiogram.types import LinkPreviewOptions, BufferedInputFile, InputFile
from aiogram.exceptions import TelegramRetryAfter, TelegramForbiddenError
from src.core.config import config
from src.core.dto import SignalDTO
from src.utils import format_smart_num

logger = logging.getLogger(__name__)

# Глобальный семафор для контроля FloodWait (~25 сообщений в секунду)
broadcaster_semaphore = asyncio.Semaphore(25)
MAX_PHOTO_CAPTION_LEN = 1024


def build_alert_payload(
    data: dict | SignalDTO,
    *,
    threshold_cascade: float | None = None,
    settings_override: dict[str, bool] | None = None,
    alert_type: str | None = None,
    alert_title: str | None = None,
) -> dict:
    if "market_data" not in data:
        payload = dict(data)
        if threshold_cascade is not None:
            payload["threshold_cascade"] = threshold_cascade
        if settings_override:
            payload.update(settings_override)
        if alert_type is not None:
            payload["alert_type"] = alert_type
        if alert_title is not None:
            payload["alert_title"] = alert_title
        return payload

    dto = data
    market_data = dto["market_data"]
    impact_metrics = dto["impact_metrics"]
    trade_metrics = dto["trade_metrics"]
    settings = dict(dto["settings"])

    if settings_override:
        settings.update(settings_override)

    return {
        "signal_id": dto["signal_id"],
        "symbol": dto["symbol"],
        "side_label": dto["side_label"],
        "alert_type": alert_type or dto["alert_type"],
        "alert_title": alert_title or dto["alert_title"],
        "sum_5m": market_data["sum_5m"],
        "sum_1h": market_data["sum_1h"],
        "sum_cascade": market_data["sum_cascade"],
        "cascade_count": market_data["cascade_count"],
        "oi_pct": market_data["oi_pct"],
        "oi_val": market_data["oi_val"],
        "price_pct": market_data["price_pct"],
        "total_oi": market_data["total_oi"],
        "funding": market_data["funding"],
        "rsi": market_data["rsi"],
        "cap_ratio": impact_metrics["cap_ratio"],
        "vol_ratio": impact_metrics["vol_ratio"],
        "live_mcap": impact_metrics["live_mcap"],
        "is_fallback": impact_metrics["is_fallback"],
        "delta_5m": trade_metrics["delta_5m"],
        "delta_30m": trade_metrics["delta_30m"],
        "show_oi": settings["show_oi"],
        "show_cvd": settings["show_cvd"],
        "show_rsi": settings["show_rsi"],
        "used_mcap": settings["used_mcap"],
        "threshold_cascade": threshold_cascade if threshold_cascade is not None else 5000.0,
        "timestamp": dto["timestamp"],
    }

class AlertFormatter:
    """Профессиональный конструктор уведомлений (SOLID)"""
    
    def __init__(self, data: dict | SignalDTO):
        self.data = build_alert_payload(data)
        self.symbol = self.data.get("symbol", "UNKNOWN")
        self.side_label = self.data.get("side_label", "UNKNOWN")

    @staticmethod
    def format_money(value: float | None) -> str:
        if value is None:
            return "$0"
        abs_val = abs(value)
        if abs_val >= 1_000_000_000:
            res = f"${abs_val / 1_000_000_000:.2f}B"
        elif abs_val >= 1_000_000:
            res = f"${abs_val / 1_000_000:.2f}M"
        elif abs_val >= 1_000:
            res = f"${abs_val / 1_000:.1f}K"
        else:
            res = f"${abs_val:.0f}"
        return f"-{res}" if value < 0 else res

    @staticmethod
    def get_trend_emoji(val: float | None) -> str:
        if val is None or val == 0: return "⚪"
        return "🟢" if val > 0 else "🔴"
    
    @staticmethod
    def get_liq_emoji(side: str) -> str:
        return "🔴" if side == "SHORT" else "🟢"

    def _header(self) -> str:
        """Сборка заголовка с маркерами аномалий"""
        alert_type = self.data.get("alert_type")
        alert_title = self.data.get("alert_title", "LIQUIDATION ALERT")
        fire = "🔥🔥" if alert_type in ["CASCADE", "OI_PUMP"] else ""
        
        side = self.data.get("side_label")
        header_emoji = "🟢" if side == "SHORT" else "🔴" 

        return f"{header_emoji} {hbold('#' + self.symbol)} {fire}\n{hbold(alert_title)}\n\n"

    def _market_block(self) -> str:
        """Блок ОИ и цены с экстремальными маркерами"""
        if not self.data.get("show_oi"): 
            return ""
        
        oi_pct = self.data.get("oi_pct")
        price_pct = self.data.get("price_pct")
        oi_val = self.data.get("oi_val")

        # Маркеры экстремальных значений (❗️ и ‼️)
        oi_pct_marker = " ❗️" if oi_pct is not None and abs(oi_pct) >= 10 else ""
        oi_val_marker = " ‼️" if oi_val is not None and abs(oi_val) >= 5_000_000 else " ❗️" if oi_val is not None and abs(oi_val) >= 1_000_000 else ""
        price_marker = " ❗️" if price_pct is not None and abs(price_pct) >= 10 else ""

        oi_display = format_smart_num(oi_pct, is_percent=True, show_sign=True) if oi_pct is not None else "⌛"
        price_display = format_smart_num(price_pct, is_percent=True, show_sign=True) if price_pct is not None else "⌛"
        price_arrow = "↗️" if (price_pct or 0) > 0 else "↘️" if (price_pct or 0) < 0 else ""

        oi_str = f"{oi_display}{oi_pct_marker}"
        if oi_val is not None and oi_val != 0:
            oi_str += f" ({self.format_money(oi_val)}{oi_val_marker})"

        res = f"{self.get_trend_emoji(oi_pct)} {hbold('OI:')} {oi_str}\n"
        res += f"{self.get_trend_emoji(price_pct)} {hbold('Price:')} {price_display}{price_marker} {price_arrow}\n"
        return res

    def _cvd_block(self) -> str:
        """Блок дельты (More Buys / More Sells)"""
        if not self.data.get("show_cvd"): 
            return ""
        
        d5 = self.data.get("delta_5m")
        d30 = self.data.get("delta_30m")
        
        res = ""
        for period, val in [("5m", d5), ("30m", d30)]:
            if val is None:
                res += f"⌛ {hbold(f'CVD ({period}):')} ⌛\n"
            elif val >= 0:
                res += f"🟢 {hbold(f'More Buys ({period}):')} {self.format_money(val)}\n"
            else:
                res += f"🔴 {hbold(f'More Sells ({period}):')} {self.format_money(abs(val))}\n"
        return res

    def _liq_block(self) -> str:
        """Блок ликвидаций"""
        sum_5m = self.data.get("sum_5m", 0.0)
        sum_1h = self.data.get("sum_1h", 0.0)
        sum_cas = self.data.get("sum_cascade", 0.0)
        count_cas = self.data.get("cascade_count", 0)
        threshold_cas = self.data.get("threshold_cascade", 5000.0)

        side_5m = self.side_label
        side_1h = self.data.get("side_label_1h", self.side_label)

        emoji_5m = self.get_liq_emoji(side_5m)
        emoji_1h = self.get_liq_emoji(side_1h)

        cascade_emoji = "🌋" if sum_cas >= (threshold_cas * 2) else "⚡️"
        
        res = ""
        if self.data.get("alert_type") == "CASCADE" or count_cas >= getattr(config, 'CASCADE_TRIGGER_COUNT', 10):
            res += f"{cascade_emoji} {hbold('LIQ CASCADE:')} x{count_cas} ({self.format_money(sum_cas)})\n"
        else:
            res = f"{emoji_5m} {hbold(f'{side_5m} LIQ (5m):')} {self.format_money(sum_5m)}\n"
            
        res += f"{emoji_1h} {hbold(f'{side_1h} LIQ (1H):')} {self.format_money(sum_1h)}\n"
        return res

    def _impact_block(self) -> str:
        """Блок рыночного влияния ликвидаций на торги за 24часа (Vol Ratio)"""
        vol_ratio = self.data.get("vol_ratio")
        if vol_ratio is None:
            return ""
        
        marker = ""
        if vol_ratio >= 10.0:
            marker = " 💎"
        elif vol_ratio >= 5.0:
            marker = " ⚠️"
        elif vol_ratio >= 1.0:
            marker = " ❗️"
            
        formatted_vol = format_smart_num(vol_ratio, is_percent=True, decimal_places=4)
        return f"🌊 {hbold('Vol Ratio:')} {formatted_vol} {marker}\n"

    def _fundamental_block(self) -> str:
        """Блок фундаментальных данных (Market Cap и Cap Ratio)"""
        live_mcap = self.data.get("live_mcap", 0.0)
        cap_ratio = self.data.get("cap_ratio")
        is_fallback = self.data.get("is_fallback", False)

        if is_fallback:
            return f"💎 {hbold('Market Cap:')} ⌛\n"
        
        if live_mcap <= 0:
            return ""

        marker = ""
        if cap_ratio is not None:
            if cap_ratio >= 0.1:
                marker = " 💎"
            elif cap_ratio >= 0.05:
                marker = " ⚠️"
            elif cap_ratio >= 0.01:
                marker = " ❗️"

        formatted_mcap = self.format_money(live_mcap)
        formatted_cap = format_smart_num(cap_ratio, is_percent=True, decimal_places=4) if cap_ratio is not None else "⌛"
        
        return (
            f"💎 {hbold('Market Cap:')} {formatted_mcap}\n"
            f"⚖ {hbold('Cap Ratio:')} {formatted_cap}{marker}\n"
        )

    def _indicators_block(self) -> str:
        """Технические индикаторы (RSI, Funding) с экстремумами"""
        rsi = self.data.get("rsi")
        funding = self.data.get("funding", 0.0)
        total_oi = self.data.get("total_oi", 0.0)
        
        res = "\n"
        if self.data.get("show_rsi") and rsi is not None:
            rsi_emoji = "⚠️" if rsi >= 70 or rsi <= 30 else "📉"
            rsi_status = " 🔥" if rsi >= 80 or rsi <= 20 else ""
            res += f"{rsi_emoji} {hbold('RSI (1H):')} {rsi}% {rsi_status}\n"
            
        fund_abs = abs(funding) if funding else 0
        fund_marker = " ‼️" if fund_abs >= 1.0 else " ❗️" if fund_abs >= 0.5 else ""
        fund_emoji = "🔴" if funding and funding < 0 else "🟢"
        
        res += f"{fund_emoji} {hbold('Funding:')} {(funding or 0):.4f}%{fund_marker}\n"
        
        if self.data.get("show_oi"):
            res += f"📶 {hbold('Total OI:')} {self.format_money(total_oi)}\n"
        return res

    def _footer(self) -> str:
        """Блок ссылок и инструкции"""
        # Ссылки на биржи
        links = (
            f"🔹 <a href='https://www.tradingview.com/chart/?symbol=BYBIT:{self.symbol}.P'><i>TradingView</i></a> | "
            f"<a href='https://www.bybit.com/trade/usdt/{self.symbol}'><i>Bybit</i></a>"
        )
        
        # Ссылка на инструкцию (Telegraph)
        guide = f"\n\n📖 {hlink('Как читать этот сигнал?/How to read this alert?', config.GUIDE_URL)}"
        
        return f"\n{links}{guide}"

    def compile_text(self, include_footer: bool = True) -> str:
        """Итоговая сборка сообщения"""
        text = (
            self._header() +
            self._market_block() +
            self._cvd_block() +
            '\n' +
            self._liq_block() +
            self._impact_block() +
            '\n' +
            self._fundamental_block() +
            self._indicators_block()
        )
        if include_footer:
            text += self._footer()
        return text


def _trim_photo_caption(formatter: AlertFormatter, full_text: str) -> str:
    if len(full_text) <= MAX_PHOTO_CAPTION_LEN:
        return full_text

    variants = [
        formatter.compile_text(include_footer=False),
        formatter._header() + formatter._market_block() + formatter._liq_block() + formatter._impact_block(),
        formatter._header() + formatter._liq_block(),
    ]

    for variant in variants:
        trimmed = variant.strip()
        if len(trimmed) <= MAX_PHOTO_CAPTION_LEN:
            return trimmed

    plain_text = re.sub(r"<[^>]+>", "", full_text)
    plain_text = re.sub(r"\n{3,}", "\n\n", plain_text).strip()
    if len(plain_text) <= MAX_PHOTO_CAPTION_LEN:
        return plain_text
    return f"{plain_text[: MAX_PHOTO_CAPTION_LEN - 1].rstrip()}…"

async def send_liquidation_alert(
    bot: Bot,
    user_id: int,
    retry_count: int = 0,
    photo_bytes: bytes | None = None,
    photo_file_id: str | None = None,
    **kwargs,
) -> str | None:
    """Единая точка входа для отправки алертов с защитой от FloodWait"""
    if retry_count > 3:
        logger.error(f"❌ Превышено число попыток отправки для {user_id}")
        return None

    async with broadcaster_semaphore:
        try:
            formatter = AlertFormatter(kwargs)
            text = formatter.compile_text()

            if photo_bytes or photo_file_id:
                caption = _trim_photo_caption(formatter, text)
                photo: InputFile | str
                if photo_bytes is not None:
                    photo = BufferedInputFile(photo_bytes, filename=f"{formatter.symbol.lower()}_chart.png")
                else:
                    photo = photo_file_id or ""

                sent_msg = await bot.send_photo(
                    chat_id=user_id,
                    photo=photo,
                    caption=caption,
                    parse_mode="HTML",
                    protect_content=True,
                )
                return sent_msg.photo[-1].file_id if sent_msg.photo else None

            await bot.send_message(
                chat_id=user_id,
                text=text,
                parse_mode="HTML",
                protect_content=True,
                link_preview_options=LinkPreviewOptions(is_disabled=True)
            )
            return None
            
        except TelegramRetryAfter as e:
            logger.warning(f"⏳ Flood limit ({e.retry_after}s) для {user_id}. Попытка #{retry_count + 1}")
            await asyncio.sleep(e.retry_after)
            return await send_liquidation_alert(
                bot,
                user_id,
                retry_count + 1,
                photo_bytes=photo_bytes,
                photo_file_id=photo_file_id,
                **kwargs,
            )
            
        except TelegramForbiddenError:
            logger.debug(f"🚫 Юзер {user_id} заблокировал бота.")
            return None
            
        except Exception as e:
            logger.error(f"❌ Ошибка Notifier для {user_id}: {e}")
            return None
