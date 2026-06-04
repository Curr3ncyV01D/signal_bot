import asyncio
import logging
from aiogram import Bot
from aiogram.utils.markdown import hbold, hlink
from aiogram.types import LinkPreviewOptions
from aiogram.exceptions import TelegramRetryAfter, TelegramForbiddenError
from src.core.config import config

logger = logging.getLogger(__name__)

# Глобальный семафор для контроля FloodWait (~25 сообщений в секунду)
broadcaster_semaphore = asyncio.Semaphore(25)

class AlertFormatter:
    """Профессиональный конструктор уведомлений (SOLID)"""
    
    def __init__(self, data: dict):
        self.data = data
        self.symbol = data.get("symbol", "UNKNOWN")
        self.side_label = data.get("side_label", "UNKNOWN")
        
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
        
        oi_pct = self.data.get("oi_pct")
        if oi_pct is None:
            header_emoji = "⚪"
        else:
            header_emoji = "🟢" if oi_pct > 0 else "🔴" if oi_pct < 0 else "⚪"

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

        oi_display = f"{oi_pct:+.2f}%" if oi_pct is not None else "⌛"
        price_display = f"{price_pct:+.2f}%" if price_pct is not None else "⌛"
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
                res += f"📊 {hbold(f'CVD ({period}):')} ⌛\n"
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

        res = f"{emoji_5m} {hbold(f'{side_5m} LIQ (5m):')} {self.format_money(sum_5m)}\n"
        
        if self.data.get("alert_type") == "CASCADE" or count_cas >= getattr(config, 'CASCADE_TRIGGER_COUNT', 10):
            res += f"{cascade_emoji} {hbold('LIQ КАСКАД:')} {count_cas} шт ({self.format_money(sum_cas)})\n"
        else:
            res += f"{emoji_1h} {hbold(f'{side_1h} LIQ 1H:')} {self.format_money(sum_1h)}\n"
        return res

    def _indicators_block(self) -> str:
        """Технические индикаторы (RSI, Funding) с экстремумами"""
        rsi = self.data.get("rsi")
        funding = self.data.get("funding", 0.0)
        total_oi = self.data.get("total_oi", 0.0)
        
        res = "\n"
        if self.data.get("show_rsi") and rsi is not None:
            rsi_emoji = "⚠️" if rsi >= 70 or rsi <= 30 else "📉"
            rsi_status = " 🔥" if rsi >= 80 or rsi <= 20 else ""
            res += f"{rsi_emoji} {hbold('RSI (5m):')} {rsi}{rsi_status}\n"
            
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
        guide = f"\n\n📖 {hlink('Как читать этот сигнал?', config.GUIDE_URL)}"
        
        return f"\n{links}{guide}"

    def compile_text(self) -> str:
        """Итоговая сборка сообщения"""
        return (
            self._header() +
            self._market_block() +
            self._cvd_block() +
            self._liq_block() +
            self._indicators_block() +
            self._footer()
        )

async def send_liquidation_alert(bot: Bot, user_id: int, **kwargs):
    """Единая точка входа для отправки алертов с защитой от FloodWait"""
    async with broadcaster_semaphore:
        try:
            formatter = AlertFormatter(kwargs)
            text = formatter.compile_text()

            await bot.send_message(
                chat_id=user_id,
                text=text,
                parse_mode="HTML",
                protect_content=True,
                link_preview_options=LinkPreviewOptions(is_disabled=True)
            )
            # Принудительная задержка для соблюдения лимитов Telegram (30/сек)
            await asyncio.sleep(0.04)
            
        except TelegramRetryAfter as e:
            logger.warning(f"Flood limit reached. Sleep for {e.retry_after}s")
            await asyncio.sleep(e.retry_after)
            # Рекурсивная попытка после паузы
            return await send_liquidation_alert(bot, user_id, **kwargs)
        except TelegramForbiddenError:
            logger.info(f"User {user_id} blocked the bot. Skipping.")
        except Exception as e:
            logger.error(f"Ошибка Notifier для {user_id}: {e}")