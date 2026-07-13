import logging

from aiogram import F, Router, types
from aiogram_i18n import I18nContext
from aiogram.types import FSInputFile, InputMediaPhoto
from aiogram.filters import Command
from aiogram.utils.markdown import hbold, hcode
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import config, ImagePaths
from src.core.localization import FALLBACK_LOCALE, DEFAULT_LOCALE, normalize_locale_code
from src.database.models import User
from src.database.crud import user_service, billing_service
from src.services.analyzer import invalidate_user_cache
from src.services.logic.billing_processor import process_payment_update
from src.utils import format_datetime, format_smart_num
from src.bot.handlers.onboarding import render_onboarding_language_screen
from src.bot.keyboards.billing_kb import (
    get_wallet_main_kb, 
    get_payment_link_kb,
    get_payment_success_kb,
    get_wallet_back_kb,
    get_subscription_tariffs_kb,
)

logger = logging.getLogger(__name__)
router = Router()


def render_wallet_text(user: User, i18n: I18nContext) -> str:
    """Формирует карточку кошелька в стилистике главного меню."""
    return i18n.get(
        "wallet-main-screen",
        balance=hbold(f"{format_smart_num(user.balance)}"),
        monthly_price=config.SUB_MONTHLY_PRICE,
        user_id=hcode(user.id),
    )


async def _render_wallet_screen(
    event: types.Message | types.CallbackQuery,
    caption: str,
    reply_markup: types.InlineKeyboardMarkup | None = None,
    image_path: str | None = None
) -> None:
    """Умный рендеринг экранов кошелька: с баннером или без него."""
    if isinstance(event, types.Message):
        if image_path:
            await event.answer_photo(
                photo=FSInputFile(image_path),
                caption=caption,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
        else:
            await event.answer(
                caption,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
        return

    if image_path:
        try:
            await event.message.edit_media(
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
            await event.message.edit_text(
                caption,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
            return
        except Exception as e:
            pass

    await event.message.delete()
    if image_path:
        await event.message.answer_photo(
            photo=FSInputFile(image_path),
            caption=caption,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
    else:
        await event.message.answer(
            caption,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )


@router.message(Command("wallet"))
async def cmd_wallet(message: types.Message, session: AsyncSession, i18n: I18nContext):
    """Главное меню кошелька"""
    user = await user_service.get_user_by_id(session, message.from_user.id)
    if not user:
        user = await user_service.get_or_create_user(
            session,
            message.from_user.id,
            message.from_user.username,
            telegram_language_code=message.from_user.language_code,
        )
    if user is None:
        await message.answer(i18n.get("profile-not-found-start"))
        return
    if not user.is_setup_completed:
        await render_onboarding_language_screen(message, i18n)
        return
    await _render_wallet_screen(message, render_wallet_text(user, i18n), get_wallet_main_kb(user), image_path=ImagePaths.WALLET)

@router.callback_query(F.data == "wallet_main")
async def callback_wallet_main(callback: types.CallbackQuery, session: AsyncSession, i18n: I18nContext):
    """Возврат в главное меню кошелька"""
    user = await user_service.get_user_by_id(session, callback.from_user.id)
    if not user:
        user = await user_service.get_or_create_user(
            session,
            callback.from_user.id,
            callback.from_user.username,
            telegram_language_code=callback.from_user.language_code,
        )
    if user is None:
        return await callback.answer(i18n.get("settings-error-profile"), show_alert=True)
    if not user.is_setup_completed:
        await render_onboarding_language_screen(callback, i18n)
        await callback.answer()
        return
    await _render_wallet_screen(callback, render_wallet_text(user, i18n), get_wallet_main_kb(user), image_path=ImagePaths.WALLET)

@router.callback_query(F.data == "change_language")
async def callback_change_language(callback: types.CallbackQuery, session: AsyncSession, i18n: I18nContext):
    """Переключает язык интерфейса пользователя между RU и EN."""
    user = await user_service.get_user_by_id(session, callback.from_user.id)
    if not user:
        return await callback.answer(i18n.get("settings-error-profile"), show_alert=True)

    current_locale = normalize_locale_code(user.language_code)
    new_locale = FALLBACK_LOCALE if current_locale == DEFAULT_LOCALE else DEFAULT_LOCALE

    user.language_code = new_locale
    await session.commit()
    await session.refresh(user)
    await invalidate_user_cache(user.id)

    with i18n.use_locale(new_locale):
        await _render_wallet_screen(
            callback,
            render_wallet_text(user, i18n),
            get_wallet_main_kb(user),
            image_path=ImagePaths.WALLET,
        )
        await callback.answer(i18n.get("wallet-language-changed"))

@router.callback_query(F.data == "toggle_auto_renewal")
async def process_toggle_auto_renewal(callback: types.CallbackQuery, session: AsyncSession, i18n: I18nContext):
    """Переключает статус автопродления в профиле пользователя."""
    user = await user_service.get_user_by_id(session, callback.from_user.id)
    if not user:
        return await callback.answer(i18n.get("settings-error-profile"), show_alert=True)

    user.auto_renewal = not user.auto_renewal
    await session.commit()
    await session.refresh(user)

    await _render_wallet_screen(callback, render_wallet_text(user, i18n), get_wallet_main_kb(user), image_path=ImagePaths.WALLET)

    status_text = (
        i18n.get("wallet-autorenew-enabled")
        if user.auto_renewal
        else i18n.get("wallet-autorenew-disabled")
    )
    await callback.answer(i18n.get("wallet-autorenew-status", status=status_text))

@router.callback_query(F.data == "tx_history")
async def callback_tx_history(callback: types.CallbackQuery, session: AsyncSession, i18n: I18nContext):
    """Показывает последние транзакции пользователя."""
    transactions = await billing_service.get_recent_transactions(session, callback.from_user.id)

    if not transactions:
        text = i18n.get("wallet-history-empty")
    else:
        blocks: list[str] = []
        for tx in transactions:
            tx_date = format_datetime(tx.created_at)
            amount = float(tx.amount)
            
            if amount > 0:
                amount_str = f"🟢 +{format_smart_num(amount)}"
            else:
                amount_str = f"🔴 {format_smart_num(amount)}"
                
            blocks.append(
                f"┌ 📅 {tx_date} │ {hbold(amount_str)} USDT\n"
                f"└ {tx.description or tx.type}"
            )
        text = i18n.get("wallet-history-title") + "\n\n" + "\n\n".join(blocks)

    await _render_wallet_screen(callback, text, get_wallet_back_kb())
    await callback.answer()

@router.callback_query(F.data == "partner_cabinet")
async def callback_partner_cabinet(callback: types.CallbackQuery, session: AsyncSession, i18n: I18nContext):
    """Показывает данные партнерской программы пользователя."""
    bot_info = await callback.bot.get_me()
    referral_link = f"https://t.me/{bot_info.username}?start={callback.from_user.id}"

    invited_count, total_rewards = await billing_service.get_partner_stats(session, callback.from_user.id)

    text = i18n.get(
        "wallet-partner-screen",
        bonus_percent=config.REFERRAL_BONUS_PERCENT,
        referral_link=hcode(referral_link),
        invited_count=hbold(str(invited_count)),
        total_rewards=hbold(f"{format_smart_num(total_rewards)} USDT"),
    )
    await _render_wallet_screen(callback, text, get_wallet_back_kb(), image_path=ImagePaths.AFFILIATE)
    await callback.answer()

@router.callback_query(F.data == "deposit")
async def callback_deposit(callback: types.CallbackQuery, i18n: I18nContext):
    """Legacy redirect: ручное пополнение удалено, ведем пользователя к выбору тарифа."""
    await callback.answer(i18n.get("wallet-deposit-removed-toast"), show_alert=True)
    await _render_wallet_screen(callback, i18n.get("shop-subscription-menu"), get_subscription_tariffs_kb())


@router.callback_query(F.data.startswith("deposit_"))
async def callback_legacy_deposit_amount(callback: types.CallbackQuery, i18n: I18nContext):
    """Legacy redirect для старых пресетов пополнения."""
    await callback.answer(i18n.get("wallet-deposit-removed-toast"), show_alert=True)
    await _render_wallet_screen(callback, i18n.get("shop-subscription-menu"), get_subscription_tariffs_kb())

@router.callback_query(F.data.startswith("check_pay_"))
async def callback_check_payment(callback: types.CallbackQuery, session: AsyncSession, i18n: I18nContext):
    """Ручная проверка оплаты инвойса"""
    try:
        external_id = callback.data.split("_", 2)[2]
    except (ValueError, IndexError):
        return await callback.answer(i18n.get("wallet-invalid-invoice-id"), show_alert=True)

    payment_result = await process_payment_update(session, external_id)

    if payment_result.is_paid:
        if payment_result.sub_activated and payment_result.new_end_date:
            await _render_wallet_screen(
                callback,
                i18n.get(
                    "wallet-subscription-paid-success-screen",
                    new_end=hbold(format_datetime(payment_result.new_end_date)),
                ),
                reply_markup=get_payment_success_kb(),
                image_path=ImagePaths.PAYMENT
            )
            return await callback.answer(i18n.get("wallet-subscription-activated-toast"))

        if (
            payment_result.intent_action == "sub"
            and not payment_result.sub_activated
            and payment_result.error == "insufficient_balance_for_intent"
        ):
            await _render_wallet_screen(
                callback,
                i18n.get(
                    "wallet-payment-price-changed-screen",
                    balance=hbold(f"{format_smart_num(payment_result.new_balance)} USDT"),
                    needed=hbold(f"{format_smart_num(payment_result.needed_amount)} USDT"),
                ),
                image_path=ImagePaths.PAYMENT,
            )
            return await callback.answer(i18n.get("wallet-payment-price-changed-toast"), show_alert=True)

        await _render_wallet_screen(
            callback,
            i18n.get(
                "wallet-balance-paid-success-screen",
                balance=hbold(f"{format_smart_num(payment_result.new_balance)} USDT"),
            ),
            image_path=ImagePaths.PAYMENT
        )
        return await callback.answer(i18n.get("wallet-success-toast"))

    if payment_result.invoice_status == 'EXPIRED':
        await _render_wallet_screen(callback, i18n.get("wallet-invoice-expired-screen"))
        return await callback.answer(i18n.get("wallet-expired-toast"))

    if payment_result.invoice_status == 'PARTIAL':
        await _render_wallet_screen(
            callback,
            i18n.get(
                "wallet-payment-partial-screen",
                paid_amount=hbold(f"{format_smart_num(payment_result.amount_actual)} USDT"),
                expected_amount=hbold(f"{format_smart_num(payment_result.amount_expected)} USDT"),
                needed_amount=hbold(f"{format_smart_num(payment_result.needed_amount)} USDT"),
            ),
            image_path=ImagePaths.PAYMENT
        )
        return await callback.answer(i18n.get("wallet-payment-partial-toast"), show_alert=True)

    if payment_result.error == "provider_error":
        return await callback.answer(i18n.get("wallet-payment-gateway-error"), show_alert=True)

    if payment_result.error == "payment_processing":
        return await callback.answer(i18n.get("wallet-payment-processing"), show_alert=True)

    await callback.answer(i18n.get("wallet-payment-not-found-yet"), show_alert=True)
