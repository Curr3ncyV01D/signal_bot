import logging
import asyncio
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.utils.markdown import hbold, hcode

from src.database.session import async_session
from src.database.crud import user_service, billing_service
from src.services.cryptopay import cryptopay
from src.bot.keyboards.billing_kb import (
    get_wallet_main_kb, 
    get_deposit_amounts_kb, 
    get_payment_link_kb
)

logger = logging.getLogger(__name__)
router = Router()

@router.message(Command("wallet"))
@router.message(F.text.contains("Кошелек"))
async def cmd_wallet(message: types.Message):
    """Главное меню кошелька"""
    async with async_session() as session:
        user = await user_service.get_user_by_id(session, message.from_user.id)
        if not user:
            user = await user_service.get_or_create_user(session, message.from_user.id, message.from_user.username)
    
    text = (
        f"💳 <b>Ваш кошелек</b>\n\n"
        f"💰 Текущий баланс: {hbold(f'{user.balance:.2f} USDT')}\n"
        f"🆔 Ваш ID: {hcode(user.id)}\n\n"
        f"Выберите действие:"
    )
    await message.answer(text, reply_markup=get_wallet_main_kb(user.balance), parse_mode="HTML")

@router.callback_query(F.data == "wallet_main")
async def callback_wallet_main(callback: types.CallbackQuery):
    """Возврат в главное меню кошелька"""
    async with async_session() as session:
        user = await user_service.get_user_by_id(session, callback.from_user.id)
    
    text = (
        f"💳 <b>Ваш кошелек</b>\n\n"
        f"💰 Текущий баланс: {hbold(f'{user.balance:.2f} USDT')}\n"
        f"🆔 Ваш ID: {hcode(user.id)}\n\n"
        f"Выберите действие:"
    )
    await callback.message.edit_text(text, reply_markup=get_wallet_main_kb(user.balance), parse_mode="HTML")

@router.callback_query(F.data == "deposit")
async def callback_deposit(callback: types.CallbackQuery):
    """Выбор суммы пополнения"""
    text = (
        f"➕ <b>Пополнение баланса</b>\n\n"
        f"Выберите сумму пополнения в USDT.\n"
        f"Оплата принимается через {hbold('CryptoBot')}."
    )
    await callback.message.edit_text(text, reply_markup=get_deposit_amounts_kb(), parse_mode="HTML")

@router.callback_query(F.data.startswith("deposit_"))
async def callback_create_invoice(callback: types.CallbackQuery):
    """Создание инвойса CryptoPay"""
    amount = float(callback.data.split("_")[1])
    user_id = callback.from_user.id
    
    # Сразу отвечаем на callback, чтобы не было "query is too old"
    await callback.answer()
    
    # 1. Создаем инвойс в CryptoBot с таймаутом
    try:
        res = await asyncio.wait_for(
            cryptopay.create_payment_invoice(amount, user_id),
            timeout=15
        )
    except asyncio.TimeoutError:
        logger.warning("CryptoPay API timeout при создании инвойса")
        return await callback.answer("❌ Таймаут CryptoPay API. Попробуйте позже.", show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка CryptoPay API: {e}")
        return await callback.answer("❌ Ошибка CryptoPay API. Попробуйте позже.", show_alert=True)
    
    if not res:
        return await callback.answer("❌ Ошибка CryptoPay API. Попробуйте позже.", show_alert=True)
    
    pay_url, invoice_id = res
    
    # 2. Сохраняем инвойс в БД
    async with async_session() as session:
        await billing_service.create_invoice(
            session=session,
            user_id=user_id,
            amount=amount,
            tariff_days=0, # Просто пополнение
            crypto_pay_id=str(invoice_id)
        )
    
    text = (
        f"🧾 <b>Счет на оплату #{invoice_id}</b>\n\n"
        f"Сумма: {hbold(f'{amount} USDT')}\n"
        f"Статус: {hbold('Ожидание оплаты')}\n\n"
        f"Нажмите кнопку ниже для перехода в CryptoBot:"
    )
    await callback.message.edit_text(text, reply_markup=get_payment_link_kb(pay_url, invoice_id), parse_mode="HTML")

@router.callback_query(F.data.startswith("check_pay_"))
async def callback_check_payment(callback: types.CallbackQuery):
    """Ручная проверка оплаты инвойса"""
    invoice_id = int(callback.data.split("_")[2])
    
    # Сразу отвечаем на callback, чтобы не было "query is too old"
    await callback.answer()
    
    # 1. Проверяем статус в API с таймаутом
    try:
        status = await asyncio.wait_for(
            cryptopay.check_invoice_status(invoice_id),
            timeout=15
        )
    except asyncio.TimeoutError:
        logger.warning("CryptoPay API timeout при проверке инвойса")
        return await callback.answer("❌ Таймаут CryptoPay API. Попробуйте позже.", show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка CryptoPay API при проверке: {e}")
        return await callback.answer("❌ Ошибка CryptoPay API. Попробуйте позже.", show_alert=True)
    
    if status == 'paid':
        # 2. Начисляем через атомарный метод
        async with async_session() as session:
            success = await billing_service.confirm_invoice_payment(session, str(invoice_id))
            if success:
                user = await user_service.get_user_by_id(session, callback.from_user.id)
                await callback.message.edit_text(
                    f"✅ <b>Оплата подтверждена!</b>\n\n"
                    f"Ваш баланс пополнен. Текущий баланс: {hbold(f'{user.balance:.2f} USDT')}",
                    parse_mode="HTML"
                )
                return await callback.answer("Успешно!")
            else:
                return await callback.answer("Ошибка при зачислении. Обратитесь в поддержку.", show_alert=True)
    
    elif status == 'expired':
        async with async_session() as session:
            await billing_service.update_invoice_status(session, str(invoice_id), 'EXPIRED')
        await callback.message.edit_text("❌ Срок действия счета истек.")
        return await callback.answer("Истек")
        
    else:
        await callback.answer("⏳ Оплата еще не обнаружена.", show_alert=True)
