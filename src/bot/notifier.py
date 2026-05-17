import logging
from aiogram import Bot
from aiogram.utils.markdown import hbold
from src.core.config import config
from aiogram.types import LinkPreviewOptions



logger = logging.getLogger(__name__)

def format_money(value: float) -> str:
    """Форматирует число в красивый вид: 1500 -> 1.5K, 1500000 -> 1.5M"""
    if value >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    elif value >= 1_000:
        return f"${value / 1_000:.1f}K"
    return f"${value:.0f}"

async def send_liquidation_alert(
    bot: Bot, 
    user_id: int, 
    symbol: str, 
    side_label: str, 
    sum_5m: float, 
    sum_1h: float, 
    sum_cascade: float,
    cascade_count: int,
    signals_24h: int
):
    """Формирует и отправляет сводное сообщение пользователю"""
    try:
        # 1. Цветовая индикация
        market_color = "🔴" if side_label == "LONG" else "🟢"
        pos_color = "🟢" if side_label == "LONG" else "🔴"
        
        # 2. Логика заголовка
        if cascade_count >= config.CASCADE_TRIGGER_COUNT:
            formatted_cas_sum = format_money(sum_cascade)
            header = f"⚡️ LIQ КАСКАД x{cascade_count} ({formatted_cas_sum})"
        elif sum_5m > (sum_1h * config.SQUEEZE_RATIO):
            header = "🔥 QUICK SQUEEZE"
        else:
            header = "📊 LIQ VOLUME"

        # 3. Красивое форматирование сумм
        formatted_5m = format_money(sum_5m)
        formatted_1h = format_money(sum_1h)

        # 4. Сборка текста сообщения
        text = f"{market_color} {hbold('#' + symbol)}\n\n"
        text += f"{hbold(header)}\n\n"
        
        # Основной блок с метриками
        text += f"{pos_color} {side_label} LIQ (5m): {hbold(formatted_5m)}\n"
        text += f"{pos_color} {side_label} LIQ (1H): {hbold(formatted_1h)}\n\n"
        
        if cascade_count >= config.CASCADE_UI_DISPLAY_COUNT:
            text += f"⚡️ {hbold('LIQ КАСКАД:')} {cascade_count} подряд\n"

        # Строка статистики
        text += f"\n🔔 {hbold('Сигналы за 24ч:')} {signals_24h}\n"

        # Ссылки 
        links = (
            f"<a href='https://www.tradingview.com/chart/?symbol=BYBIT:{symbol}.P'><i>📈 TradingView</i></a> | "
            f"<a href='https://www.bybit.com/trade/usdt/{symbol}'><i>🏛 Bybit</i></a>")
        text += f"\n🔹 {links}"

        # 5. Отправка пользователю
        await bot.send_message(
            chat_id=user_id,
            text=text,
            parse_mode="HTML",
            protect_content=True,
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения пользователю {user_id}: {e}")