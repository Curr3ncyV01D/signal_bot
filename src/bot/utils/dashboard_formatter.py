import logging
from datetime import datetime, timedelta, timezone
from aiogram.utils.markdown import hbold, hlink

logger = logging.getLogger(__name__)

class DashboardFormatter:
    """
    Класс для форматирования текста продвинутого аналитического дэшборда.
    """

    @staticmethod
    def format_money(value: float) -> str:
        """
        Форматирует числа: до $1k -> целое, от $1k до $1M -> $150.5K, от $1M -> $1.52M.
        """
        try:
            abs_val = abs(value)
            if abs_val >= 1_000_000:
                res = f"${value / 1_000_000:.2f}M"
            elif abs_val >= 1_000:
                res = f"${value / 1_000:.1f}K"
            else:
                res = f"${value:.0f}"
            return res
        except Exception as e:
            logger.error(f"Ошибка format_money: {e}")
            return str(value)

    @staticmethod
    def format_percent(value: float) -> str:
        """
        Возвращает строку вида +1.2% или -0.5%.
        """
        try:
            sign = "+" if value > 0 else ""
            return f"{sign}{value:.1f}%"
        except Exception as e:
            logger.error(f"Ошибка format_percent: {e}")
            return str(value)

    @staticmethod
    def get_time_header(window_minutes: int) -> str:
        """
        Формирует заголовок с интервалом (например, "19:00–19:15 · 07.06.2026 · MSK (UTC+3)").
        """
        try:
            now_utc = datetime.now(timezone.utc)
            now_msk = now_utc + timedelta(hours=3)
            start_msk = now_msk - timedelta(minutes=window_minutes)
            
            time_range = f"{start_msk.strftime('%H:%M')}–{now_msk.strftime('%H:%M')}"
            date_str = now_msk.strftime("%d.%m.%Y")
            
            return f"{time_range} · {date_str} · MSK (UTC+3)"
        except Exception as e:
            logger.error(f"Ошибка get_time_header: {e}")
            return "??:??–??:?? · ??.??.???? · MSK (UTC+3)"

    @classmethod
    def compile_dashboard(cls, data: dict, window_minutes: int) -> str:
        """
        Собирает итоговый HTML-текст дэшборда.
        """
        try:
            lines = []
            
            # 1. & 2. Заголовки
            lines.append(f"{hbold(f'📊 Статистика за · {window_minutes}м')}")
            lines.append(f"⏱️ {cls.get_time_header(window_minutes)}")
            
            # 3. Инфо об обновлении
            lines.append("🔄 Этот пост обновляется каждую минуту. Окно анализа: 15м.")
            lines.append("") # Разделитель
            
            # 4. Long liquidations
            lines.append(f"🟢 {hbold('Ликвидации LONG: (Топ-10)')}")
            longs = data.get("longs", [])
            if longs:
                for i, (symbol, val) in enumerate(longs, 1):
                    lines.append(f"{i}. #{symbol} — {hbold(cls.format_money(val))}")
            else:
                lines.append("<i>Данные собираются... ⌛</i>")
            lines.append("")
            
            # 5. Short liquidations
            lines.append(f"🔴 {hbold('Ликвидации SHORT: (Топ-10)')}")
            shorts = data.get("shorts", [])
            if shorts:
                for i, (symbol, val) in enumerate(shorts, 1):
                    lines.append(f"{i}. #{symbol} — {hbold(cls.format_money(val))}")
            else:
                lines.append("<i>Данные собираются... ⌛</i>")
            lines.append("")
            
            # 6. Top Open Interest Header
            lines.append(f"💥 {hbold(f'Топ Открытого Интереса · {window_minutes}м')}")
            
            # 7. OI UP
            lines.append(f"🟢 {hbold('OI UP: (Топ-20)')}")
            oi_up = data.get("oi_up", [])
            if oi_up:
                for i, (symbol, pct, delta, current) in enumerate(oi_up, 1):
                    lines.append(
                        f"{i}. #{symbol}: {hbold(cls.format_percent(pct))} "
                        f"({cls.format_money(delta)}) · {cls.format_money(current)}"
                    )
            else:
                lines.append("<i>Данные собираются... ⌛</i>")
            lines.append("")
            
            # 8. OI DOWN
            lines.append(f"🔴 {hbold('OI DOWN: (Топ-20)')}")
            oi_down = data.get("oi_down", [])
            if oi_down:
                for i, (symbol, pct, delta, current) in enumerate(oi_down, 1):
                    lines.append(
                        f"{i}. #{symbol}: {hbold(cls.format_percent(pct))} "
                        f"({cls.format_money(delta)}) · {cls.format_money(current)}"
                    )
            else:
                lines.append("<i>Данные собираются... ⌛</i>")
            lines.append("")
            
            # 9. Total OI Summary
            total_oi_raw = data.get("total_oi_current")
            if total_oi_raw is not None and total_oi_raw > 0:
                total_oi = cls.format_money(total_oi_raw)
                total_pct = cls.format_percent(data.get("total_oi_pct_change", 0.0))
                lines.append(f"📊 {hbold('Total OI:')} {total_oi} ({total_pct} vs window start)")
            else:
                lines.append(f"📊 {hbold('Total OI:')}   <i>Данные собираются... ⌛</i>")
            lines.append("")
            
            # 10. RSI Heatmap
            lines.append(f"🧭 {hbold('Тепловая карта RSI · 1 час (RSI14)')}")
            
            # Overbought
            lines.append(f"🟢 {hbold('RSI выше 80 (Топ-10)')}")
            overbought = data.get("rsi_overbought", [])
            if overbought:
                for i, (symbol, val) in enumerate(overbought, 1):
                    lines.append(f"{i}. #{symbol} — RSI {hbold(str(val))}")
            else:
                lines.append("<i>Данные собираются... ⌛</i>")
                
            # Oversold
            lines.append(f"🔴 {hbold('RSI ниже 20 (Топ-10)')}")
            oversold = data.get("rsi_oversold", [])
            if oversold:
                for i, (symbol, val) in enumerate(oversold, 1):
                    lines.append(f"{i}. #{symbol} — RSI {hbold(str(val))}")
            else:
                lines.append("<i>Данные собираются... ⌛</i>")
            lines.append("")
            
            # 11. BTC Data Footer
            btc_price = data.get("btc_price", 0.0)
            btc_change = data.get("btc_change_1h")
            btc_url = "https://www.bybit.com/trade/usdt/BTCUSDT"
            btc_link = hlink(f"${btc_price:,.0f}", btc_url)
            
            btc_change_str = cls.format_percent(btc_change) if btc_change is not None else "Сбор данных %..."
            lines.append(f"🟡 ₿ {hbold('BTC:')} {btc_link} ({btc_change_str} vs предыдущий час закрытия)")
            lines.append("")
            
            # 12. Next update
            now = datetime.now(timezone.utc) + timedelta(hours=3)
            next_minutes = (now.minute // 15 + 1) * 15
            next_time = now.replace(minute=0, second=0, microsecond=0) + timedelta(minutes=next_minutes)
            
            lines.append(f"⏭️ {hbold('⏭ Следующее обновление:')} {next_time.strftime('%H:%M')}")
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"Критическая ошибка compile_dashboard: {e}", exc_info=True)
            return f"❌ {hbold('Ошибка генерации дэшборда')}\n<i>Попробуйте позже...</i>"
