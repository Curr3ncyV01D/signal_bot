import io
import csv
import logging
import asyncio
import time
from datetime import datetime, timezone
from aiogram import Router, types, F
from aiogram.utils.markdown import hbold
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext

from src.database.session import async_session
from src.bot.filters.admin import IsAdminFilter
from src.services.metrics_service import MetricsService
from src.bot.utils.admin_bi_formatter import BIFormatter
from src.bot.keyboards.admin_bi_kb import (
    get_bi_main_kb, get_bi_finance_kb, 
    get_bi_audience_kb, get_bi_system_kb
)
from src.bot.keyboards.main_kb import get_back_button_kb
from src.database.crud.billing_service import get_all_deposits
from src.bot.handlers.admin import AdminChannelStates

logger = logging.getLogger(__name__)

router = Router()
router.message.filter(IsAdminFilter())
router.callback_query.filter(IsAdminFilter())

@router.callback_query(F.data == "admin_bi_main")
async def process_admin_bi_main(callback: types.CallbackQuery):
    """Главный экран BI-аналитики"""
    text = (
        f"📊 {hbold('Дэшборд бизнес-аналитики')}\n\n"
        f"Добро пожаловать в центр управления данными. "
        f"Выберите раздел ниже для получения детальной статистики:"
    )
    await callback.message.edit_text(text, reply_markup=get_bi_main_kb(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "admin_bi_finance")
async def process_bi_finance(callback: types.CallbackQuery, listener, liq_aggregator, data_queue: asyncio.Queue):
    """Экран финансовых метрик"""
    async with async_session() as session:
        data = await MetricsService.get_admin_bi_data(
            session, listener, liq_aggregator, data_queue
        )
        
    text = BIFormatter.format_finance_text(data['financial'])
    try:
        await callback.message.edit_text(text, reply_markup=get_bi_finance_kb(), parse_mode="HTML")
    except TelegramBadRequest:
        pass
    await callback.answer()

@router.callback_query(F.data == "admin_bi_audience")
async def process_bi_audience(callback: types.CallbackQuery, listener, liq_aggregator, data_queue: asyncio.Queue):
    """Экран метрик аудитории"""
    async with async_session() as session:
        data = await MetricsService.get_admin_bi_data(
            session, listener, liq_aggregator, data_queue
        )
        
    text = BIFormatter.format_audience_text(data['audience'])
    try:
        await callback.message.edit_text(text, reply_markup=get_bi_audience_kb(), parse_mode="HTML")
    except TelegramBadRequest:
        pass
    await callback.answer()

@router.callback_query(F.data == "admin_bi_system")
async def process_bi_system(callback: types.CallbackQuery, listener, liq_aggregator, data_queue: asyncio.Queue):
    """Экран системных метрик"""
    async with async_session() as session:
        data = await MetricsService.get_admin_bi_data(
            session, listener, liq_aggregator, data_queue
        )
        
    text = BIFormatter.format_system_text(data['tech'])
    try:
        await callback.message.edit_text(text, reply_markup=get_bi_system_kb(), parse_mode="HTML")
    except TelegramBadRequest:
        pass
    await callback.answer()

@router.callback_query(F.data == "admin_bi_export_csv")
async def process_bi_export_csv(callback: types.CallbackQuery):
    """Экспорт истории транзакций (DEPOSIT) в CSV"""
    await callback.answer("⏳ Формирую отчет...")
    
    async with async_session() as session:
        deposits = await get_all_deposits(session)
        
    if not deposits:
        return await callback.message.answer("❌ Нет данных для экспорта (транзакции DEPOSIT отсутствуют).")

    # Генерация CSV в памяти
    output = io.StringIO()
    # utf-8-sig для корректного открытия в Excel с кириллицей
    writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_MINIMAL)
    
    # Заголовки
    writer.writerow(["ID транзакции", "Дата (UTC)", "User ID", "Username", "Сумма (USDT)", "Описание"])
    
    for tx in deposits:
        username = f"@{tx.user.username}" if tx.user and tx.user.username else "N/A"
        writer.writerow([
            tx.id,
            tx.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            tx.user_id,
            username,
            tx.amount,
            tx.description or ""
        ])
    
    # Подготовка файла для отправки
    filename = f"payments_report_{datetime.now().strftime('%Y-%m-%d')}.csv"
    csv_bytes = output.getvalue().encode('utf-8-sig')
    input_file = types.BufferedInputFile(csv_bytes, filename=filename)
    
    await callback.message.answer_document(
        document=input_file,
        caption=f"📊 <b>Отчет по депозитам</b>\nВсего записей: {len(deposits)}",
        parse_mode="HTML"
    )

@router.callback_query(F.data == "admin_bi_symbol_search")
async def process_bi_symbol_search_btn(callback: types.CallbackQuery, state: FSMContext):
    """Начало поиска монеты"""
    await callback.message.answer(
        "🔍 Введите тикер монеты для поиска (например, BTC или PEPEUSDT):",
        reply_markup=get_back_button_kb("admin_bi_system")
    )
    await state.set_state(AdminChannelStates.waiting_for_symbol_search)
    await callback.answer()

@router.message(AdminChannelStates.waiting_for_symbol_search)
async def process_bi_symbol_search_input(message: types.Message, state: FSMContext, listener):
    """Обработка ввода тикера для поиска"""
    symbol = message.text.strip().upper()
    if not symbol.endswith("USDT"):
        symbol += "USDT"

    info = listener.get_detailed_symbol_info(symbol)
    
    if info:
        last_hb = info.get("last_heartbeat")
        if last_hb:
            pulse_text = f"{int(time.time() - last_hb)} сек. назад"
        else:
            pulse_text = "Нет данных"
            
        status_icon = "✅ Отслеживается" if info.get("is_connected") else "❌ Не отслеживается"
        
        market_status = info.get("market_status", "Unknown")
        status_mapping = {
            "Trading": "🟢 ТОРГУЕТСЯ",
            "PreLaunch": "⏳ PRE-LAUNCH (Ожидание торгов)",
            "Settling": "🔴 ТОРГИ ПРИОСТАНОВЛЕНЫ",
            "Closed": "🔴 ТОРГИ ПРИОСТАНОВЛЕНЫ"
        }
        market_status_text = status_mapping.get(market_status, f"❓ {market_status}")

        text = (
            f"💰 <b>Монета:</b> #{symbol}\n"
            f"📦 <b>Сокет:</b> Чанк №{info.get('chunk_index')}\n"
            f"🌐 <b>Статус:</b> {status_icon}\n"
            f"📊 <b>Статус рынка:</b> {market_status_text}\n"
            f"💓 <b>Пульс:</b> {pulse_text}"
        )
    else:
        text = f"❌ Монета {hbold(symbol)} не найдена в списке отслеживаемых."

    await message.answer(
        text, 
        reply_markup=get_back_button_kb("admin_bi_system"),
        parse_mode="HTML"
    )
    await state.clear()

@router.callback_query(F.data == "admin_bi_symbol_export")
async def process_bi_symbol_export(callback: types.CallbackQuery, listener):
    """Экспорт списка всех отслеживаемых монет в TXT"""
    await callback.answer("⏳ Генерирую список...")
    
    grouped_data = listener.get_all_tracked_grouped()
    total_symbols = sum(len(syms) for syms in grouped_data.values())
    total_sockets = len(grouped_data)
    
    now = datetime.now().strftime("%H:%M %d.%m.%Y")
    
    output = io.StringIO()
    output.write(f"=== ОТЧЕТ ПО МОНИТОРИНГУ РЫНКА [{now}] ===\n")
    output.write(f"Всего отслеживается: {total_symbols} монет\n")
    output.write(f"Активных соединений: {total_sockets}\n")
    output.write("-" * 42 + "\n\n")
    
    for chunk_idx, symbols in grouped_data.items():
        formatted_symbols = []
        for s in symbols:
            status = listener.symbol_statuses.get(s, "")
            if status == "PreLaunch":
                formatted_symbols.append(f"{s} [PL]")
            else:
                formatted_symbols.append(s)
        
        symbols_str = ", ".join(formatted_symbols)
        output.write(f"Socket #{chunk_idx} ({len(symbols)}): {symbols_str}\n\n")
    
    output.write("-" * 42 + "\n")
    output.write("Легенда:\n")
    output.write("[PL] = Монета в статусе PreLaunch (ожидание торгов)\n")
    
    filename = f"market_audit_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
    file_bytes = output.getvalue().encode('utf-8')
    input_file = types.BufferedInputFile(file_bytes, filename=filename)
    
    await callback.message.answer_document(
        document=input_file,
        caption=f"📄 <b>Полный аудит рынка</b>\nВсего: {total_symbols} монет в {total_sockets} сокетах.",
        parse_mode="HTML"
    )
