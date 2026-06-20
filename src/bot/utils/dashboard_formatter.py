import logging
import math
from datetime import datetime, timedelta, timezone
from aiogram.utils.markdown import hbold, hlink

logger = logging.getLogger(__name__)
TELEGRAM_TEXT_SAFE_LIMIT = 3950
TRUNCATED_NOTICE = "⚠️ Часть данных обрезана из-за лимитов Telegram"

class DashboardFormatter:
    """
    Класс для форматирования текста продвинутого аналитического дэшборда.
    """

    @staticmethod
    def format_money(value: float | None) -> str:
        """
        Форматирует числа: до $1k -> целое, от $1k до $1M -> $150.5K, от $1M -> $1.52M.
        """
        if value is None:
            return "$0"
        try:
            num = float(value)
        except (TypeError, ValueError):
            return "$0"

        if not math.isfinite(num) or num == 0.0:
            return "$0"

        abs_val = abs(num)
        if abs_val >= 1_000_000:
            return f"${num / 1_000_000:.2f}M"
        if abs_val >= 1_000:
            return f"${num / 1_000:.1f}K"
        return f"${num:.0f}"

    @staticmethod
    def format_percent(value: float | None) -> str:
        """
        Возвращает строку вида +1.2% или -0.5%.
        """
        if value is None:
            return "0.0%"
        try:
            num = float(value)
        except (TypeError, ValueError):
            return "0.0%"

        if not math.isfinite(num) or num == 0.0:
            return "0.0%"

        sign = "+" if num > 0 else ""
        return f"{sign}{num:.1f}%"

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
            get_data = data.get
            format_money = cls.format_money
            format_percent = cls.format_percent
            sections: list[tuple[str, list[str], bool]] = []

            header_lines = [
                f"{hbold(f'📊 Статистика за · {window_minutes}м')}",
                f"⏱️ {cls.get_time_header(window_minutes)}",
                "🔄 Этот пост обновляется каждую минуту. Окно анализа: 15м.",
                "",
            ]
            sections.append(("header", header_lines, False))

            long_lines = [f"🟢 {hbold('Ликвидации LONG: (Топ-10)')}"]
            longs = get_data("longs", [])
            if longs:
                for i, (symbol, val) in enumerate(longs, 1):
                    long_lines.append(f"{i}. #{symbol} — {hbold(format_money(val))}")
            else:
                long_lines.append("<i>Данные собираются... ⌛</i>")
            long_lines.append("")
            sections.append(("longs", long_lines, False))

            short_lines = [f"🔴 {hbold('Ликвидации SHORT: (Топ-10)')}"]
            shorts = get_data("shorts", [])
            if shorts:
                for i, (symbol, val) in enumerate(shorts, 1):
                    short_lines.append(f"{i}. #{symbol} — {hbold(format_money(val))}")
            else:
                short_lines.append("<i>Данные собираются... ⌛</i>")
            short_lines.append("")
            sections.append(("shorts", short_lines, False))

            oi_up_lines = [
                f"💥 {hbold(f'Топ Открытого Интереса · {window_minutes}м')}",
                f"🟢 {hbold('OI UP: (Топ-20)')}",
            ]
            oi_up = get_data("oi_up", [])
            if oi_up:
                for i, (symbol, pct, delta, current) in enumerate(oi_up, 1):
                    oi_up_lines.append(
                        f"{i}. #{symbol}: {hbold(format_percent(pct))} "
                        f"({format_money(delta)}) · {format_money(current)}"
                    )
            else:
                oi_up_lines.append("<i>Данные собираются... ⌛</i>")
            oi_up_lines.append("")
            sections.append(("oi_up", oi_up_lines, False))

            oi_down_lines = [f"🔴 {hbold('OI DOWN: (Топ-20)')}"]
            oi_down = get_data("oi_down", [])
            if oi_down:
                for i, (symbol, pct, delta, current) in enumerate(oi_down, 1):
                    oi_down_lines.append(
                        f"{i}. #{symbol}: {hbold(format_percent(pct))} "
                        f"({format_money(delta)}) · {format_money(current)}"
                    )
            else:
                oi_down_lines.append("<i>Данные собираются... ⌛</i>")
            oi_down_lines.append("")
            sections.append(("oi_down", oi_down_lines, True))

            summary_lines = []
            total_oi_raw = get_data("total_oi_current")
            if total_oi_raw is not None and total_oi_raw > 0:
                total_oi = format_money(total_oi_raw)
                total_pct_raw = get_data("total_oi_pct_change")
                if total_pct_raw is not None:
                    total_pct = format_percent(total_pct_raw)
                    summary_lines.append(f"📊 {hbold('Total OI:')} {total_oi} ({total_pct} vs 15 минут назад)")
                else:
                    summary_lines.append(f"📊 {hbold('Total OI:')} {total_oi} (анализ динамики... ⌛)")
            else:
                summary_lines.append(f"📊 {hbold('Total OI:')}   <i>Данные собираются... ⌛</i>")
            summary_lines.append("")
            sections.append(("summary", summary_lines, False))

            rsi_overbought_lines = [
                f"🧭 {hbold('Тепловая карта RSI · 1 час (RSI14)')}",
                f"🟢 {hbold('RSI выше 80 (Топ-10)')}",
            ]
            overbought = get_data("rsi_overbought", [])
            if overbought:
                for i, (symbol, val) in enumerate(overbought, 1):
                    rsi_overbought_lines.append(f"{i}. #{symbol} — RSI {hbold(str(val))}")
            else:
                rsi_overbought_lines.append("<i>Данные собираются... ⌛</i>")
            sections.append(("rsi_overbought", rsi_overbought_lines, True))

            rsi_oversold_lines = [f"🔴 {hbold('RSI ниже 20 (Топ-10)')}"]
            oversold = get_data("rsi_oversold", [])
            if oversold:
                for i, (symbol, val) in enumerate(oversold, 1):
                    rsi_oversold_lines.append(f"{i}. #{symbol} — RSI {hbold(str(val))}")
            else:
                rsi_oversold_lines.append("<i>Данные собираются... ⌛</i>")
            rsi_oversold_lines.append("")
            sections.append(("rsi_oversold", rsi_oversold_lines, True))

            btc_lines = []
            btc_price = get_data("btc_price", 0.0)
            btc_change = get_data("btc_change_1h")
            btc_url = "https://www.bybit.com/trade/usdt/BTCUSDT"
            try:
                btc_price_num = float(btc_price)
            except (TypeError, ValueError):
                btc_price_num = 0.0

            if math.isfinite(btc_price_num) and btc_price_num > 0:
                btc_price_formatted = f"${btc_price_num:,.0f}"
                btc_link = hlink(btc_price_formatted, btc_url)
                if btc_change is not None:
                    btc_change_formatted = format_percent(btc_change)
                    btc_lines.append(f"₿ {hbold('BTC:')} {btc_link} ({btc_change_formatted} vs час назад)")
                else:
                    btc_lines.append(f"₿ {hbold('BTC:')} {btc_link} (анализ динамики... ⌛)")
            else:
                btc_lines.append(f"₿ {hbold('BTC:')} <i>Ожидание тикера... ⌛</i>")
            btc_lines.append("")
            sections.append(("btc", btc_lines, False))

            now = datetime.now(timezone.utc) + timedelta(hours=3)
            next_minutes = (now.minute // 15 + 1) * 15
            next_time = now.replace(minute=0, second=0, microsecond=0) + timedelta(minutes=next_minutes)
            footer_lines = [f"⏭️ {hbold('Следующее обновление:')} {next_time.strftime('%H:%M')}"]
            sections.append(("footer", footer_lines, False))

            def render(active_sections: list[tuple[str, list[str], bool]], truncated: bool) -> str:
                lines = [line for _, section_lines, _ in active_sections for line in section_lines]
                if truncated:
                    lines.extend(["", TRUNCATED_NOTICE])
                return "\n".join(lines)

            message = render(sections, truncated=False)
            if len(message) <= TELEGRAM_TEXT_SAFE_LIMIT:
                return message

            removable_order = ["rsi_oversold", "rsi_overbought", "oi_down", "oi_up", "shorts", "longs"]
            active_sections = sections[:]
            truncated = False

            for section_name in removable_order:
                active_sections = [section for section in active_sections if section[0] != section_name]
                truncated = True
                message = render(active_sections, truncated=True)
                if len(message) <= TELEGRAM_TEXT_SAFE_LIMIT:
                    return message

            emergency_sections = [
                section for section in sections if section[0] in {"header", "summary", "btc", "footer"}
            ]
            return render(emergency_sections, truncated=True)
        except Exception as e:
            logger.error(f"Критическая ошибка compile_dashboard: {e}", exc_info=True)
            return f"❌ {hbold('Ошибка генерации дэшборда')}\n<i>Попробуйте позже...</i>"
