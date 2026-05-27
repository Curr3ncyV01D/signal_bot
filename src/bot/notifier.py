import logging
from aiogram import Bot
from aiogram.utils.markdown import hbold
from aiogram.types import LinkPreviewOptions
from src.core.config import config

logger = logging.getLogger(__name__)

def format_money(value: float) -> str:
    """Форматирует число в красивый вид: 1500 -> $1.5K, 1500000 -> $1.50M"""
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

def get_trend_emoji(val: float) -> str:
    """🟢 для роста, 🔴 для падения, ⚪ для флета"""
    return "🟢" if val > 0 else "🔴" if val < 0 else "⚪"

async def send_liquidation_alert(
    bot: Bot, 
    user_id: int, 
    symbol: str, 
    side_label: str, 
    alert_title: str,
    sum_5m: float, 
    sum_1h: float, 
    sum_cascade: float,
    cascade_count: int,
    alert_type: str,
    oi_pct: float,
    oi_val: float,
    price_pct: float,
    total_oi: float,
    funding: float,
    delta_5m: float,  # Чистая дельта за 5м (покупки минус продажи)
    delta_30m: float, # Чистая дельта за 30м (покупки минус продажи)
    rsi: float | None = None
):
    """Формирует и отправляет красивое аналитическое сообщение пользователю"""
    try:
        # 1. Цветовая индикация стороны ликвидации (Buy ордер закрывает Short и наоборот)
        liq_color = "🔴" if side_label == "LONG" else "🟢"
        
        # 2. Оформление заголовка под тип сигнала
        fire_emoji = "🔥🔥" if alert_type in ["CASCADE", "OI_PUMP"] else ""
        text = f"{liq_color} {hbold('#' + symbol)} {fire_emoji}\n\n"
        text += f"{hbold(alert_title)}\n\n"
        
        # 3. Блок Открытого Интереса и Цены (с динамическими трендами)
        oi_sign = "+" if oi_pct > 0 else ""
        oi_str = f"{oi_sign}{oi_pct:.2f}% ({format_money(oi_val)})"
        text += f"{get_trend_emoji(oi_pct)} {hbold('OI:')} {oi_str}\n"
        
        price_sign = "+" if price_pct > 0 else ""
        text += f"{get_trend_emoji(price_pct)} {hbold('Price:')} {price_sign}{price_pct:.2f}%\n"

        # 4. Блок CVD (Дельты объемов маркет-ордеров)
        # Умный вывод: если дельта >, пишем More Buys, если <, то More Sells
        if delta_5m >= 0:
            text += f"🟢 {hbold('More Buys (5m):')} {format_money(delta_5m)}\n"
        else:
            text += f"🔴 {hbold('More Sells (5m):')} {format_money(abs(delta_5m))}\n"

        if delta_30m >= 0:
            text += f"🟢 {hbold('More Buys (30m):')} {format_money(delta_30m)}\n"
        else:
            text += f"🔴 {hbold('More Sells (30m):')} {format_money(abs(delta_30m))}\n"

        # 5. Блок Ликвидаций (Stage 1)
        text += f"{liq_color} {hbold(side_label + ' LIQ (5min):')} {format_money(sum_5m)}\n"
        
        # Если это каскад — выводим каскадную строку
        if alert_type == "CASCADE" or cascade_count >= config.CASCADE_TRIGGER_COUNT:
            formatted_cas_sum = format_money(sum_cascade)
            text += f"⚡️ {hbold('LIQ КАСКАД:')} {cascade_count} подряд ({formatted_cas_sum})\n"
        else:
            text += f"📊 {hbold(side_label + ' LIQ 1H:')} {format_money(sum_1h)}\n"

        text += "\n"

        # 6. Блок Технических Индикаторов (RSI, Funding, Total OI)
        if rsi is not None:
            # Предупреждающий эмодзи для зон перекупленности/перепроданности
            rsi_emoji = "⚠️" if rsi >= 70 or rsi <= 30 else "📉"
            text += f"{rsi_emoji} {hbold('RSI (5m):')} {rsi}\n"
            
        # Индикация знака фандинга (отрицательный фандинг подсвечиваем)
        fund_emoji = "🔴" if funding < 0 else "🟢"
        text += f"{fund_emoji} {hbold('Funding:')} {funding:.4f}%\n"
        text += f"📊 {hbold('Total OI:')} {format_money(total_oi)}\n"

        # 7. Ссылки
        links = (
            f"<a href='https://www.tradingview.com/chart/?symbol=BYBIT:{symbol}.P'><i>📈 TradingView</i></a> | "
            f"<a href='https://www.bybit.com/trade/usdt/{symbol}'><i>🏛 Bybit</i></a>")
        text += f"\n🔹 {links}"

        # 8. Отправка
        await bot.send_message(
            chat_id=user_id,
            text=text,
            parse_mode="HTML",
            protect_content=True,
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения пользователю {user_id}: {e}", exc_info=True)