import logging
from uuid import uuid4

import orjson
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram_i18n import I18nContext
from aiogram.types import FSInputFile, InputMediaPhoto
from aiogram.utils.markdown import hbold, hcode
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.keyboards import get_close_button_kb
from src.bot.keyboards.billing_kb import (
    get_balance_purchase_confirm_kb,
    get_manual_payment_kb,
    get_payment_success_kb,
    get_subscription_tariffs_kb,
)
from src.bot.handlers.admin_payments import send_payment_review_card
from src.core.config import config, ImagePaths
from src.database.crud import billing_service, user_service
from src.services.analyzer import invalidate_user_cache
from src.utils import format_datetime, format_smart_num

logger = logging.getLogger(__name__)
router = Router()
PAYLOAD_ACTION_SUB = "sub"
MANUAL_PAYMENT_PROVIDER = "MANUAL"
MANUAL_PAYMENT_NETWORK = "TRC20"
MANUAL_UPLOAD_ALLOWED_STATUSES = {"PENDING", "PARTIAL"}


class ManualPaymentStates(StatesGroup):
    waiting_for_screenshot = State()


def _format_plan_label(days: int, i18n: I18nContext) -> str:
    if days % 30 == 0:
        months = days // 30
        return i18n.get("kb-wallet-plan-months", months=months)
    return i18n.get("kb-wallet-plan-days", days=days)


def _get_subscription_menu_text(i18n: I18nContext) -> str:
    return i18n.get("shop-subscription-menu")


def _build_subscription_payload(days: int) -> str:
    return orjson.dumps(
        {
            "a": PAYLOAD_ACTION_SUB,
            "d": days,
        }
    ).decode("utf-8")


def _build_manual_invoice_external_id(user_id: int) -> str:
    return f"manual_{user_id}_{uuid4().hex[:20]}"


def _extract_intent_days(payload: str | None) -> int | None:
    if not payload:
        return None
    try:
        loaded = orjson.loads(payload)
    except orjson.JSONDecodeError:
        return None
    if not isinstance(loaded, dict):
        return None
    try:
        return int(loaded.get("d")) if loaded.get("d") is not None else None
    except (TypeError, ValueError):
        return None


async def _start_manual_payment_flow(
    callback: types.CallbackQuery,
    session: AsyncSession,
    i18n: I18nContext,
    *,
    days: int,
) -> None:
    """Создает manual invoice и показывает пользователю только ручной сценарий оплаты."""
    if not config.PAYMENT_MANUAL_WALLET or not config.ADMIN_PAYMENT_CHAT_ID:
        await callback.answer(i18n.get("shop-manual-payment-unavailable"), show_alert=True)
        return

    price = config.TARIFFS.get(days)
    user_id = callback.from_user.id
    if not price:
        await callback.answer(i18n.get("shop-plan-not-found"), show_alert=True)
        return

    user = await user_service.get_user_by_id(session, user_id)
    if not user:
        await callback.answer(i18n.get("profile-not-found-start"), show_alert=True)
        return

    plan_label = _format_plan_label(days, i18n)
    price = round(float(price), 2)
    current_balance = round(float(user.balance), 2)
    if current_balance >= price:
        text = i18n.get(
            "shop-balance-purchase-confirm",
            balance=hbold(f"{format_smart_num(current_balance)} USDT"),
            plan_label=hbold(plan_label),
            price=hbold(f"{format_smart_num(price)} USDT"),
        )
        await _render_shop_screen(callback, text, get_balance_purchase_confirm_kb(days))
        await callback.answer()
        return

    amount_to_pay = round(price - current_balance, 2)
    payload = _build_subscription_payload(days=days)
    external_id = _build_manual_invoice_external_id(user_id)
    invoice = await billing_service.create_invoice(
        session=session,
        user_id=user_id,
        external_id=external_id,
        amount_expected=amount_to_pay,
        provider=MANUAL_PAYMENT_PROVIDER,
        address=config.PAYMENT_MANUAL_WALLET,
        network=MANUAL_PAYMENT_NETWORK,
        payload=payload,
    )
    if invoice is None:
        await callback.answer(i18n.get("wallet-payment-gateway-error"), show_alert=True)
        return

    invoice_id = external_id.split("_")[-1]

    text = i18n.get(
        "shop-manual-pay-screen",
        plan_label=plan_label,
        invoice_id=hcode(invoice_id),
        price=hbold(f"{format_smart_num(price)} USDT"),
        balance=hbold(f"{format_smart_num(current_balance)} USDT"),
        amount_to_pay=hbold(f"{format_smart_num(amount_to_pay)} USDT"),
        network=MANUAL_PAYMENT_NETWORK,
        wallet=hcode(config.PAYMENT_MANUAL_WALLET),
    )
    await _render_shop_screen(
        callback,
        text,
        reply_markup=get_manual_payment_kb(external_id),
        image_path=ImagePaths.PAYMENT_QR,
    )
    await callback.answer()


def _resolve_manual_upload_error_key(invoice) -> str:
    if invoice is None:
        return "wallet-invoice-not-found"

    status = str(invoice.status or "").upper()
    if status == "WAITING_ADMIN":
        return "shop-manual-payment-already-submitted"
    if status == "PAID":
        return "shop-manual-payment-already-approved"
    if status == "EXPIRED":
        return "shop-manual-payment-expired"
    if status not in MANUAL_UPLOAD_ALLOWED_STATUSES:
        return "shop-manual-payment-upload-unavailable"
    return ""


def _extract_manual_screenshot_file_id(message: types.Message) -> str | None:
    if message.photo:
        return message.photo[-1].file_id

    document = message.document
    if document and str(document.mime_type or "").lower().startswith("image/"):
        return document.file_id

    return None


async def _render_shop_screen(
    callback: types.CallbackQuery,
    caption: str,
    reply_markup: None = None,
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
    """Target-Action Flow покупки тарифа: с баланса или manual payment."""
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
    current_balance = round(float(user.balance), 2)

    if current_balance >= price:
        text = i18n.get(
            "shop-balance-purchase-confirm",
            balance=hbold(f"{format_smart_num(current_balance)} USDT"),
            plan_label=hbold(plan_label),
            price=hbold(f"{format_smart_num(price)} USDT"),
        )
        await _render_shop_screen(callback, text, get_balance_purchase_confirm_kb(days))
        return await callback.answer()

    await _start_manual_payment_flow(
        callback,
        session,
        i18n,
        days=days,
    )


@router.callback_query(F.data.startswith("pay_cryptomus_"))
async def callback_pay_cryptomus(callback: types.CallbackQuery, session: AsyncSession, i18n: I18nContext):
    """Legacy callback: старые кнопки ведут в единственный доступный manual flow."""
    try:
        days = int(callback.data.split("_")[2])
    except (ValueError, IndexError):
        return await callback.answer(i18n.get("shop-invalid-plan-params"), show_alert=True)

    await _start_manual_payment_flow(
        callback,
        session,
        i18n,
        days=days,
    )


@router.callback_query(F.data.startswith("pay_manual_"))
async def callback_pay_manual(callback: types.CallbackQuery, session: AsyncSession, i18n: I18nContext):
    """Создание инвойса MANUAL и вывод реквизитов холодного кошелька."""
    try:
        days = int(callback.data.split("_")[2])
    except (ValueError, IndexError):
        return await callback.answer(i18n.get("shop-invalid-plan-params"), show_alert=True)

    await _start_manual_payment_flow(
        callback,
        session,
        i18n,
        days=days,
    )


@router.callback_query(F.data.startswith("manual_upload_"))
async def callback_start_manual_upload(
    callback: types.CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    i18n: I18nContext,
):
    """Переводит пользователя в состояние ожидания скриншота оплаты."""
    try:
        external_id = callback.data.split("_", 2)[2]
    except (ValueError, IndexError):
        return await callback.answer(i18n.get("wallet-invalid-invoice-id"), show_alert=True)

    invoice = await billing_service.get_invoice_by_external_id(session, external_id)
    if (
        not invoice
        or invoice.user_id != callback.from_user.id
        or str(invoice.provider or "").upper() != MANUAL_PAYMENT_PROVIDER
    ):
        return await callback.answer(i18n.get("wallet-invoice-not-found"), show_alert=True)

    error_key = _resolve_manual_upload_error_key(invoice)
    if error_key:
        return await callback.answer(i18n.get(error_key), show_alert=True)

    await state.set_state(ManualPaymentStates.waiting_for_screenshot)
    await state.update_data(manual_invoice_external_id=external_id)
    await callback.answer(i18n.get("shop-manual-payment-screenshot-prompt"), show_alert=True)


@router.message(ManualPaymentStates.waiting_for_screenshot)
async def process_manual_payment_screenshot(
    message: types.Message,
    state: FSMContext,
    session: AsyncSession,
    i18n: I18nContext,
):
    """Принимает скриншот оплаты и отправляет заявку в админ-чат."""
    screenshot_file_id = _extract_manual_screenshot_file_id(message)
    if screenshot_file_id is None:
        return await message.answer(i18n.get("shop-manual-payment-photo-only"))

    state_data = await state.get_data()
    external_id = state_data.get("manual_invoice_external_id")
    if not external_id:
        await state.clear()
        return await message.answer(i18n.get("wallet-invoice-not-found"))

    invoice = await billing_service.get_invoice_by_external_id(session, str(external_id))
    if (
        not invoice
        or invoice.user_id != message.from_user.id
        or str(invoice.provider or "").upper() != MANUAL_PAYMENT_PROVIDER
    ):
        await state.clear()
        return await message.answer(i18n.get("wallet-invoice-not-found"))

    error_key = _resolve_manual_upload_error_key(invoice)
    if error_key:
        await state.clear()
        return await message.answer(i18n.get(error_key))

    updated_invoice = await billing_service.update_invoice_record(
        session=session,
        invoice_id=invoice.id,
        amount_actual=invoice.amount_actual,
        status="WAITING_ADMIN",
    )
    if updated_invoice is None:
        await state.clear()
        return await message.answer(i18n.get("wallet-invoice-not-found"))

    updated_invoice = await billing_service.update_invoice_review_metadata(
        session=session,
        invoice_id=invoice.id,
        approved_by_admin_id=None,
        screenshot_file_id=screenshot_file_id,
        rejection_reason=None,
    )
    if updated_invoice is None:
        await state.clear()
        return await message.answer(i18n.get("wallet-invoice-not-found"))

    review_external_id = updated_invoice.external_id
    review_user_id = int(updated_invoice.user_id)
    review_amount_actual = float(updated_invoice.amount_actual)
    review_amount_expected = float(updated_invoice.amount_expected)
    review_status = str(updated_invoice.status)
    review_screenshot_file_id = str(updated_invoice.screenshot_file_id or screenshot_file_id)
    review_plan_days = _extract_intent_days(updated_invoice.payload)

    await session.commit()

    try:
        await send_payment_review_card(
            message.bot,
            invoice_external_id=review_external_id,
            invoice_user_id=review_user_id,
            invoice_amount_actual=review_amount_actual,
            invoice_amount_expected=review_amount_expected,
            invoice_status=review_status,
            screenshot_file_id=review_screenshot_file_id,
            username=message.from_user.username,
            plan_days=review_plan_days,
        )
    except Exception as exc:
        logger.error("Не удалось отправить заявку на ручную проверку ext_id=%s: %s", external_id, exc)

    await state.clear()
    await message.answer(i18n.get("shop-manual-payment-request-accepted"), parse_mode="HTML")

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

    await _render_shop_screen(
        callback,
        text,
        reply_markup=get_payment_success_kb(),
        image_path=ImagePaths.PAYMENT
    )
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
