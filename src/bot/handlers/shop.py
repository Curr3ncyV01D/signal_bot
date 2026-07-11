import asyncio
import logging

from aiogram import Router, types, F
from aiogram_i18n import I18nContext
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


def _format_plan_label(days: int, i18n: I18nContext) -> str:
    if days % 30 == 0:
        months = days // 30
        return i18n.get("kb-wallet-plan-months", months=months)
    return i18n.get("kb-wallet-plan-days", days=days)


def _get_subscription_menu_text(i18n: I18nContext) -> str:
    return i18n.get("shop-subscription-menu")


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
    session: AsyncSession,
    referrer_id: int | None,
    bonus_amount: float,
    i18n: I18nContext,
) -> None:
    if not referrer_id or bonus_amount <= 0:
        return

    try:
        referrer = await user_service.get_user_by_id(session, referrer_id)
        referrer_locale = getattr(referrer, "language_code", i18n.locale) if referrer else i18n.locale
        with i18n.use_locale(referrer_locale):
            text = i18n.get(
                "shop-referral-bonus-notification",
                bonus_amount=hbold(f"{format_smart_num(bonus_amount)} USDT"),
            )
        await callback.bot.send_message(
            chat_id=referrer_id,
            text=text,
            parse_mode="HTML",
            reply_markup=get_close_button_kb()
        )
    except Exception as e:
        logger.error(f"Не удалось уведомить реферера {referrer_id} о бонусе: {e}")


@router.callback_query(F.data == "buy_subscription")
async def callback_buy_subscription(callback: types.CallbackQuery, i18n: I18nContext):
    """Меню выбора тарифа"""
    await _render_shop_screen(
        callback,
        _get_subscription_menu_text(i18n),
        get_subscription_tariffs_kb()
    )
    await callback.answer()

@router.callback_query(F.data.startswith("buy_plan_"))
async def callback_process_purchase(callback: types.CallbackQuery, session: AsyncSession, i18n: I18nContext):
    """Процесс выбора тарифа: списание с баланса или fallback в Direct Pay."""
    try:
        days = int(callback.data.split("_")[2])
    except (ValueError, IndexError):
        return await callback.answer(i18n.get("shop-invalid-plan-params"), show_alert=True)

    price = config.TARIFFS.get(days)
    user_id = callback.from_user.id

    if not price:
        return await callback.answer(i18n.get("shop-plan-not-found"), show_alert=True)

    user = await user_service.get_user_by_id(session, user_id)
    if not user:
        return await callback.answer(i18n.get("profile-not-found-start"), show_alert=True)

    plan_label = _format_plan_label(days, i18n)
    price = round(float(price), 2)

    if round(float(user.balance), 2) >= price:
        text = i18n.get(
            "shop-balance-purchase-confirm",
            balance=hbold(f"{format_smart_num(user.balance)} USDT"),
            plan_label=hbold(plan_label),
            price=hbold(f"{format_smart_num(price)} USDT"),
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
        return await callback.answer(i18n.get("wallet-cryptopay-timeout"), show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка CryptoPay API при создании инвойса на подписку: {e}")
        return await callback.answer(i18n.get("wallet-cryptopay-error"), show_alert=True)

    if not res:
        return await callback.answer(i18n.get("wallet-cryptopay-error"), show_alert=True)

    pay_url, invoice_id = res
    await billing_service.create_invoice(
        session=session,
        user_id=user_id,
        amount=price,
        crypto_pay_id=str(invoice_id),
        payload=f"sub_{days}"
    )

    text = i18n.get(
        "shop-direct-pay-screen",
        plan_label=plan_label,
        price=hbold(f"{format_smart_num(price)} USDT"),
        balance=hbold(f"{format_smart_num(user.balance)} USDT"),
    )
    await _render_shop_screen(callback, text, get_payment_link_kb(pay_url, invoice_id))

@router.callback_query(F.data.startswith("confirm_balance_purchase_"))
async def callback_confirm_balance_purchase(callback: types.CallbackQuery, session: AsyncSession, i18n: I18nContext):
    """Подтвержденная покупка подписки с внутреннего баланса."""
    try:
        days = int(callback.data.split("_")[3])
    except (ValueError, IndexError):
        return await callback.answer(i18n.get("shop-invalid-plan-params"), show_alert=True)

    price = config.TARIFFS.get(days)
    user_id = callback.from_user.id
    if not price:
        return await callback.answer(i18n.get("shop-plan-not-found"), show_alert=True)

    success, new_end, bonus_amount = await billing_service.purchase_subscription(session, user_id, days, price)
    if not success or not new_end:
        return await callback.answer(i18n.get("shop-insufficient-balance"), show_alert=True)
        
    await invalidate_user_cache()
    purchaser = await user_service.get_user_by_id(session, user_id)
    referrer_id = purchaser.referrer_id if purchaser else None
    text = i18n.get(
        "shop-purchase-success",
        new_end=hbold(format_datetime(new_end)),
        price=hbold(f"{format_smart_num(price)} USDT"),
    )

    await _render_shop_screen(callback, text, image_path=ImagePaths.PAYMENT)
    await callback.answer(i18n.get("shop-subscription-extended"))

    await _send_referral_bonus_notification(callback, session, referrer_id, bonus_amount, i18n)

@router.callback_query(F.data == "cancel_balance_purchase")
async def callback_cancel_balance_purchase(callback: types.CallbackQuery, i18n: I18nContext):
    """Отмена быстрого продления и возврат к выбору тарифов."""
    await _render_shop_screen(
        callback,
        _get_subscription_menu_text(i18n),
        get_subscription_tariffs_kb()
    )
    await callback.answer(i18n.get("shop-purchase-cancelled"))
