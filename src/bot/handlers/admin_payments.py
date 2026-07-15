import logging
from html import escape

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.utils.markdown import hbold, hcode
from aiogram_i18n import I18nContext
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.filters.admin import IsAdminFilter
from src.bot.keyboards.billing_kb import get_manual_payment_kb
from src.core.i18n_runtime import background_i18n
from src.core.localization import DEFAULT_LOCALE, normalize_locale_code
from src.core.config import config
from src.database.crud import billing_service, user_service
from src.database.models import User
from src.services.logic.billing_processor import process_manual_approval
from src.utils import format_datetime, format_smart_num, parse_numeric_input

logger = logging.getLogger(__name__)

router = Router()
router.message.filter(IsAdminFilter())
router.callback_query.filter(IsAdminFilter())

MANUAL_PAYMENT_PROVIDER = "MANUAL"
MANUAL_PAYMENT_NETWORK = "TRC20"


class AdminManualPaymentStates(StatesGroup):
    waiting_for_custom_amount = State()
    waiting_for_rejection_reason = State()


def _is_admin_payment_chat(chat_id: int | None) -> bool:
    return bool(config.ADMIN_PAYMENT_CHAT_ID and chat_id == config.ADMIN_PAYMENT_CHAT_ID)


def _get_admin_text(key: str, **kwargs: object) -> str:
    return background_i18n.get(key, locale=DEFAULT_LOCALE, **kwargs)


def _format_admin_actor(user: types.User) -> str:
    if user.username:
        return f"@{user.username} (ID: {user.id})"
    return f"{user.full_name} (ID: {user.id})"


def _build_user_profile_link(user_id: int) -> str:
    return f'<a href="tg://user?id={user_id}">{escape(_get_admin_text("admin-pay-user-profile-link"))}</a>'


def _append_processed_by_line(text: str, admin_actor: str) -> str:
    return "\n".join(
        [
            text,
            "",
            _get_admin_text(
                "admin-pay-review-processed-by",
                admin=hbold(escape(admin_actor)),
            ),
        ]
    )


async def _lock_review_card(message: types.Message | None, admin_actor: str) -> None:
    if message is None or not message.caption:
        return
    try:
        await message.edit_caption(
            caption="\n".join(
                [
                    message.caption,
                    "",
                    _get_admin_text(
                        "admin-pay-review-processing",
                        admin=hbold(escape(admin_actor)),
                    ),
                ]
            ),
            parse_mode="HTML",
            reply_markup=None,
        )
    except Exception as exc:
        logger.debug("Не удалось перевести review-card в режим обработки: %s", exc)


def _build_review_keyboard(external_id: str, approve_amount: float) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=_get_admin_text(
                "kb-admin-pay-approve",
                amount=f"{format_smart_num(approve_amount)} USDT",
            ),
            callback_data=f"admin_pay_approve:{external_id}",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=_get_admin_text("kb-admin-pay-custom"),
            callback_data=f"admin_pay_custom:{external_id}",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=_get_admin_text("kb-admin-pay-reject"),
            callback_data=f"admin_pay_reject:{external_id}",
        )
    )
    return builder.as_markup()


async def send_payment_review_card(
    bot,
    *,
    invoice_external_id: str,
    invoice_user_id: int,
    invoice_amount_actual: float,
    invoice_amount_expected: float,
    invoice_status: str,
    screenshot_file_id: str,
    username: str | None,
    plan_days: int | None,
) -> None:
    if not config.ADMIN_PAYMENT_CHAT_ID or not screenshot_file_id:
        return

    plan_text = f"{plan_days} дн." if plan_days else "N/A"
    username_text = f"@{username}" if username else "—"
    already_paid_amount = max(round(float(invoice_amount_actual), 2), 0.0)
    needed_amount = max(round(float(invoice_amount_expected) - already_paid_amount, 2), 0.0)
    is_topup = already_paid_amount > 0
    title_key = "admin-pay-review-card-title-topup" if is_topup else "admin-pay-review-card-title-new"
    approve_amount = needed_amount if is_topup and needed_amount > 0 else float(invoice_amount_expected)

    lines = [
        _get_admin_text(title_key),
        "",
        f"User ID: {hcode(str(invoice_user_id))}",
        f"Username: {username_text}",
        _build_user_profile_link(invoice_user_id),
        "",
        f"Invoice: {hcode(invoice_external_id)}",
        f"Сумма к подтверждению: {hbold(f'{format_smart_num(invoice_amount_expected)} USDT')}",
    ]
    if is_topup:
        lines.extend(
            [
                _get_admin_text(
                    "admin-pay-review-card-already-paid",
                    amount=hbold(f"{format_smart_num(already_paid_amount)} USDT"),
                ),
                _get_admin_text(
                    "admin-pay-review-card-needed",
                    amount=hbold(f"{format_smart_num(needed_amount)} USDT"),
                ),
            ]
        )
    lines.extend(
        [
            f"Тариф: {hbold(plan_text)}",
            f"Статус: {hbold(invoice_status)}",
        ]
    )
    caption = "\n".join(lines)
    await bot.send_photo(
        chat_id=config.ADMIN_PAYMENT_CHAT_ID,
        photo=screenshot_file_id,
        caption=caption,
        parse_mode="HTML",
        reply_markup=_build_review_keyboard(invoice_external_id, approve_amount),
    )


async def _notify_user_about_manual_result(
    bot,
    *,
    user: User,
    payment_result,
    invoice_external_id: str,
    rejection_reason: str | None = None,
) -> None:
    user_locale = normalize_locale_code(user.language_code)
    if rejection_reason is not None:
        text = background_i18n.get(
            "manual-payment-rejected-notification",
            locale=user_locale,
            reason=rejection_reason,
        )
        await bot.send_message(chat_id=user.id, text=text, parse_mode="HTML")
        return

    if payment_result.sub_activated and payment_result.new_end_date:
        text = background_i18n.get(
            "payment-worker-subscription-paid-notification",
            locale=user_locale,
            amount=f"{format_smart_num(payment_result.delta_credited or payment_result.amount_actual)} USDT",
            days=payment_result.intent_days or 0,
            new_end=format_datetime(payment_result.new_end_date),
        )
    elif payment_result.intent_action == "sub" and payment_result.is_paid and not payment_result.sub_activated:
        text = background_i18n.get(
            "payment-worker-price-changed-notification",
            locale=user_locale,
            balance=f"{format_smart_num(payment_result.new_balance)} USDT",
            needed=f"{format_smart_num(payment_result.needed_amount)} USDT",
        )
    elif payment_result.delta_credited > 0 and not payment_result.is_paid and payment_result.amount_actual > 0:
        text = background_i18n.get(
            "payment-worker-partial-payment-notification",
            locale=user_locale,
            paid_amount=f"{format_smart_num(payment_result.amount_actual)} USDT",
            expected_amount=f"{format_smart_num(payment_result.amount_expected)} USDT",
            needed_amount=f"{format_smart_num(payment_result.needed_amount)} USDT",
            network=MANUAL_PAYMENT_NETWORK,
            wallet=hcode(config.PAYMENT_MANUAL_WALLET or "—"),
        )
        await bot.send_message(
            chat_id=user.id,
            text=text,
            parse_mode="HTML",
            reply_markup=get_manual_payment_kb(
                invoice_external_id,
                screenshot_button_key="kb-wallet-send-topup-screenshot",
            ),
        )
        return
    else:
        text = background_i18n.get(
            "manual-payment-approved-notification",
            locale=user_locale,
            amount=f"{format_smart_num(payment_result.delta_credited or payment_result.amount_actual)} USDT",
            balance=f"{format_smart_num(payment_result.new_balance)} USDT",
        )

    await bot.send_message(chat_id=user.id, text=text, parse_mode="HTML")


async def _get_manual_invoice(session: AsyncSession, ext_id: str):
    invoice = await billing_service.get_invoice_by_external_id(session, ext_id)
    if not invoice:
        return None
    if (invoice.provider or "").upper() != MANUAL_PAYMENT_PROVIDER:
        return None
    return invoice


def _render_admin_result_text(ext_id: str, amount_actual: float, payment_result, admin_actor: str) -> str:
    parts = [
        _get_admin_text("admin-pay-review-result-title"),
        "",
        f"Invoice: {hcode(ext_id)}",
        f"Статус: {hbold(payment_result.invoice_status)}",
        "",
        f"Подтверждено: {hbold(f'{format_smart_num(amount_actual)} USDT')}",
        "",
        f"Баланс после активации подписки: {hbold(f'{format_smart_num(payment_result.new_balance)} USDT')}",
    ]
    if payment_result.sub_activated and payment_result.new_end_date:
        parts.append(
            _get_admin_text(
                "admin-pay-review-result-subscription",
                new_end=hbold(format_datetime(payment_result.new_end_date)),
            )
        )
    elif payment_result.error:
        parts.append(
            _get_admin_text(
                "admin-pay-review-result-error",
                error=hcode(payment_result.error),
            )
        )
    return _append_processed_by_line("\n".join(parts), admin_actor)


def _render_admin_rejection_text(ext_id: str, rejection_reason: str, admin_actor: str) -> str:
    return _append_processed_by_line(
        _get_admin_text(
            "admin-pay-review-rejected",
            invoice_id=hcode(ext_id),
            reason=hbold(escape(rejection_reason)),
        ),
        admin_actor,
    )


@router.callback_query(F.data.startswith("admin_pay_approve:"))
async def process_admin_payment_approve(
    callback: types.CallbackQuery,
    session: AsyncSession,
    i18n: I18nContext,
):
    if not _is_admin_payment_chat(callback.message.chat.id if callback.message else None):
        return await callback.answer(i18n.get("admin-pay-wrong-chat"), show_alert=True)

    ext_id = callback.data.split(":", maxsplit=1)[1]
    invoice = await _get_manual_invoice(session, ext_id)
    if not invoice:
        return await callback.answer(i18n.get("admin-pay-invoice-not-found"), show_alert=True)
    already_paid = invoice.status == "PAID"
    if already_paid:
        return await callback.answer(i18n.get("admin-pay-already-processed"), show_alert=True)

    admin_actor = _format_admin_actor(callback.from_user)
    await _lock_review_card(callback.message, admin_actor)

    user = await user_service.get_user_by_id(session, invoice.user_id)
    payment_result = await process_manual_approval(
        session=session,
        ext_id=ext_id,
        admin_id=callback.from_user.id,
        amount_actual=float(invoice.amount_expected),
        admin_name=admin_actor,
    )

    if user and not already_paid:
        try:
            await _notify_user_about_manual_result(
                callback.bot,
                user=user,
                payment_result=payment_result,
                invoice_external_id=ext_id,
            )
        except Exception as exc:
            logger.error("Не удалось уведомить пользователя %s о ручном подтверждении: %s", user.id, exc)

    await callback.message.edit_caption(
        caption=_render_admin_result_text(ext_id, float(invoice.amount_expected), payment_result, admin_actor),
        parse_mode="HTML",
        reply_markup=None,
    )
    await callback.answer(i18n.get("admin-pay-approve-done"))


@router.callback_query(F.data.startswith("admin_pay_custom:"))
async def process_admin_payment_custom_start(
    callback: types.CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    i18n: I18nContext,
):
    if not _is_admin_payment_chat(callback.message.chat.id if callback.message else None):
        return await callback.answer(i18n.get("admin-pay-wrong-chat"), show_alert=True)

    ext_id = callback.data.split(":", maxsplit=1)[1]
    invoice = await _get_manual_invoice(session, ext_id)
    if not invoice:
        return await callback.answer(i18n.get("admin-pay-invoice-not-found"), show_alert=True)
    if invoice.status == "PAID":
        return await callback.answer(i18n.get("admin-pay-already-processed"), show_alert=True)

    admin_actor = _format_admin_actor(callback.from_user)
    await _lock_review_card(callback.message, admin_actor)

    await state.set_state(AdminManualPaymentStates.waiting_for_custom_amount)
    await state.update_data(
        manual_payment_ext_id=ext_id,
        manual_payment_card_message_id=callback.message.message_id if callback.message else None,
        manual_payment_admin_actor=admin_actor,
    )
    await callback.message.answer(
        i18n.get(
            "admin-pay-custom-amount-prompt",
            invoice_id=hcode(ext_id),
            expected_amount=hbold(f"{format_smart_num(invoice.amount_expected)} USDT"),
        ),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminManualPaymentStates.waiting_for_custom_amount)
async def process_admin_payment_custom_amount(
    message: types.Message,
    state: FSMContext,
    session: AsyncSession,
    i18n: I18nContext,
):
    if not _is_admin_payment_chat(message.chat.id):
        return await message.answer(i18n.get("admin-pay-wrong-chat"))

    data = await state.get_data()
    ext_id = data.get("manual_payment_ext_id")
    card_message_id = data.get("manual_payment_card_message_id")
    admin_actor = str(data.get("manual_payment_admin_actor") or _format_admin_actor(message.from_user))
    if not ext_id:
        await state.clear()
        return await message.answer(i18n.get("admin-pay-invoice-not-found"))

    try:
        amount_actual = parse_numeric_input(message.text or "")
    except ValueError:
        return await message.answer(i18n.get("admin-pay-custom-amount-invalid"))

    invoice = await _get_manual_invoice(session, str(ext_id))
    if not invoice:
        await state.clear()
        return await message.answer(i18n.get("admin-pay-invoice-not-found"))
    already_paid = invoice.status == "PAID"
    if already_paid:
        await state.clear()
        return await message.answer(i18n.get("admin-pay-already-processed"))

    user = await user_service.get_user_by_id(session, invoice.user_id)
    payment_result = await process_manual_approval(
        session=session,
        ext_id=str(ext_id),
        admin_id=message.from_user.id,
        amount_actual=amount_actual,
        admin_name=admin_actor,
    )

    if user and not already_paid:
        try:
            await _notify_user_about_manual_result(
                message.bot,
                user=user,
                payment_result=payment_result,
                invoice_external_id=str(ext_id),
            )
        except Exception as exc:
            logger.error("Не удалось уведомить пользователя %s о кастомном подтверждении: %s", user.id, exc)

    if card_message_id:
        try:
            await message.bot.edit_message_caption(
                chat_id=message.chat.id,
                message_id=int(card_message_id),
                caption=_render_admin_result_text(str(ext_id), amount_actual, payment_result, admin_actor),
                parse_mode="HTML",
                reply_markup=None,
            )
        except Exception as exc:
            logger.error("Не удалось обновить карточку ручного платежа ext_id=%s: %s", ext_id, exc)

    await state.clear()
    await message.answer(i18n.get("admin-pay-approve-done"))


@router.callback_query(F.data.startswith("admin_pay_reject:"))
async def process_admin_payment_reject(
    callback: types.CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    i18n: I18nContext,
):
    if not _is_admin_payment_chat(callback.message.chat.id if callback.message else None):
        return await callback.answer(i18n.get("admin-pay-wrong-chat"), show_alert=True)

    ext_id = callback.data.split(":", maxsplit=1)[1]
    invoice = await _get_manual_invoice(session, ext_id)
    if not invoice:
        return await callback.answer(i18n.get("admin-pay-invoice-not-found"), show_alert=True)
    if invoice.status == "PAID":
        return await callback.answer(i18n.get("admin-pay-already-processed"), show_alert=True)

    admin_actor = _format_admin_actor(callback.from_user)
    await _lock_review_card(callback.message, admin_actor)
    await state.set_state(AdminManualPaymentStates.waiting_for_rejection_reason)
    await state.update_data(
        manual_payment_ext_id=ext_id,
        manual_payment_card_message_id=callback.message.message_id if callback.message else None,
        manual_payment_admin_actor=admin_actor,
    )
    await callback.message.answer(i18n.get("admin-pay-enter-rejection-reason"))
    await callback.answer()


@router.message(AdminManualPaymentStates.waiting_for_rejection_reason)
async def process_admin_payment_rejection_reason(
    message: types.Message,
    state: FSMContext,
    session: AsyncSession,
    i18n: I18nContext,
):
    if not _is_admin_payment_chat(message.chat.id):
        return await message.answer(i18n.get("admin-pay-wrong-chat"))

    rejection_reason = (message.text or "").strip()
    if not rejection_reason:
        return await message.answer(i18n.get("admin-pay-enter-rejection-reason"))

    data = await state.get_data()
    ext_id = data.get("manual_payment_ext_id")
    card_message_id = data.get("manual_payment_card_message_id")
    admin_actor = str(data.get("manual_payment_admin_actor") or _format_admin_actor(message.from_user))
    if not ext_id:
        await state.clear()
        return await message.answer(i18n.get("admin-pay-invoice-not-found"))

    invoice = await _get_manual_invoice(session, str(ext_id))
    if not invoice:
        await state.clear()
        return await message.answer(i18n.get("admin-pay-invoice-not-found"))
    if invoice.status == "PAID":
        await state.clear()
        return await message.answer(i18n.get("admin-pay-already-processed"))

    user = await user_service.get_user_by_id(session, invoice.user_id)
    updated_invoice = await billing_service.reset_invoice_for_retry(
        session=session,
        invoice_id=invoice.id,
    )
    if updated_invoice is None:
        await state.clear()
        return await message.answer(i18n.get("admin-pay-invoice-not-found"))

    updated_review = await billing_service.update_invoice_review_metadata(
        session=session,
        invoice_id=invoice.id,
        approved_by_admin_id=message.from_user.id,
        screenshot_file_id=None,
        rejection_reason=rejection_reason,
    )
    if updated_review is None:
        await state.clear()
        return await message.answer(i18n.get("admin-pay-invoice-not-found"))

    await session.commit()

    if user:
        try:
            await _notify_user_about_manual_result(
                message.bot,
                user=user,
                payment_result=None,
                invoice_external_id=str(ext_id),
                rejection_reason=rejection_reason,
            )
        except Exception as exc:
            logger.error("Не удалось уведомить пользователя %s об отклонении: %s", user.id, exc)

    if card_message_id:
        try:
            await message.bot.edit_message_caption(
                chat_id=message.chat.id,
                message_id=int(card_message_id),
                caption=_render_admin_rejection_text(str(ext_id), rejection_reason, admin_actor),
                parse_mode="HTML",
                reply_markup=None,
            )
        except Exception as exc:
            logger.error("Не удалось обновить карточку отклоненного ручного платежа ext_id=%s: %s", ext_id, exc)

    await state.clear()
    await message.answer(i18n.get("admin-pay-reject-done"))
