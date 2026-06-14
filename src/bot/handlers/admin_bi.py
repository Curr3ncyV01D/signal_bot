import io
import csv
import logging
import asyncio
from datetime import datetime, timezone
from aiogram import Router, types, F
from aiogram.utils.markdown import hbold
from aiogram.exceptions import TelegramBadRequest

from src.database.session import async_session
from src.bot.filters.admin import IsAdminFilter
from src.services.metrics_service import MetricsService
from src.bot.utils.admin_bi_formatter import BIFormatter
from src.bot.keyboards.admin_bi_kb import (
    get_bi_main_kb, get_bi_finance_kb, 
    get_bi_audience_kb, get_bi_system_kb
)
from src.database.crud.billing_service import get_all_deposits

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
