import asyncio
import logging

from aiogram import Router, types, F
from aiogram.types import FSInputFile, InputMediaPhoto
from aiogram.utils.markdown import hbold
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.keyboards import get_close_button_kb
from src.bot.keyboards.billing_kb import (
    get_balance_purchase_confirm_kb,
    get_payment_link_kb,
    get_subscription_tariffs_kb,
)
from src.core.config import config, ImagePaths
from src.database.crud import billing_service, user_service
from src.services.analyzer import invalidate_user_cache
from src.services.cryptopay import cryptopay
from src.utils import format_datetime, format_smart_num

logger = logging.getLogger(__name__)
router = Router()


def _format_plan_label(days: int) -> str:
    if days % 30 == 0:
        months = days // 30
        if months == 1:
            return "1 месяц"
        if 2 <= months <= 4:
            return f"{months} месяца"
        return f"{months} месяцев"
    return f"{days} дней"


def _get_subscription_menu_text() -> str:
    return (
        "💎 <b>VIP-Подписка</b>\n\n"
        "Преимущества VIP-доступа:\n"
        "• Доступ в закрытый канал с алертами\n"
        "• Персональные настройки в боте\n"
        "• Аналитика в реальном времени\n\n"
        "Выберите подходящий тариф:"
    )


async def _render_shop_screen(
    callback: types.CallbackQuery,
    caption: str,
    reply_markup=None,
    image_path: str | None = None
) -> None:
    """Умный рендеринг экранов подписки: с баннером или без него."""
    if image_path:
        try:
            await callback.message.edit_media(
                media=InputMediaPhoto(
                    media=FSInputFile(image_path),
                    caption=caption,
                    parse_mode="HTML"
                ),
                reply_markup=reply_markup
            )
            return
        except Exception as e:
            pass
    else:
        try:
            await callback.message.edit_text(
                caption,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
            return
        except Exception as e:
            pass

    await callback.message.delete()
    if image_path:
        await callback.message.answer_photo(
            photo=FSInputFile(image_path),
            caption=caption,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
    else:
        await callback.message.answer(
            caption,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )


async def _send_referral_bonus_notification(
    callback: types.CallbackQuery,
    referrer_id: int | None,
    bonus_amount: float
) -> None:
    if not referrer_id or bonus_amount <= 0:
        return

    try:
        await callback.bot.send_message(
            chat_id=referrer_id,
            text=(
                "🤝 <b>Партнерский бонус начислен!</b>\n\n"
                f"Ваш реферал совершил покупку, и вам начислено {hbold(f'{format_smart_num(bonus_amount)} USDT')}."
            ),
            parse_mode="HTML",
            reply_markup=get_close_button_kb()
        )
    except Exception as e:
        logger.error(f"Не удалось уведомить реферера {referrer_id} о бонусе: {e}")


async def _build_invite_link_text(callback: types.CallbackQuery, user_id: int) -> str:
    if config.PRIVATE_CHANNEL_ID is None:
        return ""

    try:
        invite_link = await callback.bot.create_chat_invite_link(
            chat_id=config.PRIVATE_CHANNEL_ID,
            name=f"Sub_{user_id}",
            creates_join_request=True
        )
        return f"\n\n👉 {hbold('Ваша ссылка для входа:')}\n{invite_link.invite_link}"
    except Exception as e:
        logger.error(f"Ошибка создания ссылки: {e}")
        return "\n\n<i>(Ошибка: Бот не смог создать ссылку. Обратитесь к админу.)</i>"

@router.callback_query(F.data == "buy_subscription")
async def callback_buy_subscription(callback: types.CallbackQuery):
    """Меню выбора тарифа"""
    await _render_shop_screen(
        callback,
        _get_subscription_menu_text(),
        get_subscription_tariffs_kb()
    )
    await callback.answer()

@router.callback_query(F.data.startswith("buy_plan_"))
async def callback_process_purchase(callback: types.CallbackQuery, session: AsyncSession):
    """Процесс выбора тарифа: списание с баланса или fallback в Direct Pay."""
    try:
        days = int(callback.data.split("_")[2])
    except (ValueError, IndexError):
        return await callback.answer("❌ Некорректные параметры тарифа.", show_alert=True)

    price = config.TARIFFS.get(days)
    user_id = callback.from_user.id

    if not price:
        return await callback.answer("Ошибка: Тариф не найден.", show_alert=True)

    user = await user_service.get_user_by_id(session, user_id)
    if not user:
        return await callback.answer("Профиль не найден. Нажмите /start.", show_alert=True)

    plan_label = _format_plan_label(days)
    price = round(float(price), 2)

    if round(float(user.balance), 2) >= price:
        text = (
            "💎 <b>Продление подписки из баланса</b>\n\n"
            f"У вас достаточно средств на балансе: {hbold(f'{format_smart_num(user.balance)} USDT')}.\n\n"
            f"Хотите продлить подписку на {hbold(plan_label)} за {hbold(f'{format_smart_num(price)} USDT')}?"
        )
        await _render_shop_screen(callback, text, get_balance_purchase_confirm_kb(days))
        return await callback.answer()

    await callback.answer()

    try:
        res = await asyncio.wait_for(
            cryptopay.create_payment_invoice(price, user_id),
            timeout=15
        )
    except asyncio.TimeoutError:
        logger.warning("CryptoPay API timeout при создании инвойса на подписку")
        return await callback.answer("❌ Таймаут CryptoPay API. Попробуйте позже.", show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка CryptoPay API при создании инвойса на подписку: {e}")
        return await callback.answer("❌ Ошибка CryptoPay API. Попробуйте позже.", show_alert=True)

    if not res:
        return await callback.answer("❌ Ошибка CryptoPay API. Попробуйте позже.", show_alert=True)

    pay_url, invoice_id = res
    await billing_service.create_invoice(
        session=session,
        user_id=user_id,
        amount=price,
        crypto_pay_id=str(invoice_id),
        payload=f"sub_{days}"
    )

    text = (
        f"💎 <b>Оплата подписки: {plan_label}</b>\n\n"
        f"💰 Стоимость: {hbold(f'{format_smart_num(price)} USDT')}\n"
        f"💳 На балансе сейчас: {hbold(f'{format_smart_num(user.balance)} USDT')}\n\n"
        "На балансе недостаточно средств, поэтому мы подготовили ссылку на оплату в CryptoBot."
    )
    await _render_shop_screen(callback, text, get_payment_link_kb(pay_url, invoice_id))

@router.callback_query(F.data.startswith("confirm_balance_purchase_"))
async def callback_confirm_balance_purchase(callback: types.CallbackQuery, session: AsyncSession):
    """Подтвержденная покупка подписки с внутреннего баланса."""
    try:
        days = int(callback.data.split("_")[3])
    except (ValueError, IndexError):
        return await callback.answer("❌ Некорректные параметры тарифа.", show_alert=True)

    price = config.TARIFFS.get(days)
    user_id = callback.from_user.id
    if not price:
        return await callback.answer("Ошибка: Тариф не найден.", show_alert=True)

    success, new_end, bonus_amount = await billing_service.purchase_subscription(session, user_id, days, price)
    if not success or not new_end:
        return await callback.answer("❌ Недостаточно средств на балансе.", show_alert=True)
        
    await invalidate_user_cache()
    purchaser = await user_service.get_user_by_id(session, user_id)
    referrer_id = purchaser.referrer_id if purchaser else None
    link_text = await _build_invite_link_text(callback, user_id)

    text = (
        "🎉 <b>Подписка успешно оформлена!</b>\n\n"
        f"📅 Срок действия до: {hbold(format_datetime(new_end))}\n"
        f"💰 Списано с баланса: {hbold(f'{format_smart_num(price)} USDT')}"
        f"{link_text}"
    )

    await _render_shop_screen(callback, text, image_path=ImagePaths.PAYMENT)
    await callback.answer("Подписка продлена")

    await _send_referral_bonus_notification(callback, referrer_id, bonus_amount)

@router.callback_query(F.data == "cancel_balance_purchase")
async def callback_cancel_balance_purchase(callback: types.CallbackQuery):
    """Отмена быстрого продления и возврат к выбору тарифов."""
    await _render_shop_screen(
        callback,
        _get_subscription_menu_text(),
        get_subscription_tariffs_kb()
    )
    await callback.answer("Покупка отменена")
