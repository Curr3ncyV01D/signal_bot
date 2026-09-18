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
    get_cactus_hosted_payment_kb,
    get_cactus_payment_kb,
    get_manual_payment_kb,
    get_payment_method_selection_kb,
    get_payment_success_kb,
    get_subscription_tariffs_kb,
)
from src.bot.handlers.admin_payments import send_payment_review_card
from src.core.config import config, ImagePaths
from src.core.redis_bus import LockResult, redis_bus
from src.database.crud import billing_service, user_service
from src.services.logic.analyzer import invalidate_user_cache
from src.services.payments.cactus_client import (
    CACTUS_MIN_AMOUNT_RUB,
    CactusAPIError,
    CactusConfigurationError,
    cactus_client,
)
from src.utils import format_datetime, format_smart_num

logger = logging.getLogger(__name__)
router = Router()
PAYLOAD_ACTION_SUB = "sub"
MANUAL_PAYMENT_PROVIDER = "MANUAL"
MANUAL_PAYMENT_NETWORK = "TRC20"
MANUAL_UPLOAD_ALLOWED_STATUSES = {"PENDING", "PARTIAL"}
CACTUS_PROVIDER = "CACTUS"
_CREATE_PAYMENT_LOCK_TTL_SEC = 10
_CREATE_PAYMENT_LOCK_KEY = "csl:lock:create_cactus:user:{user_id}"


class ManualPaymentStates(StatesGroup):
    waiting_for_screenshot = State()


def _format_plan_label(days: int, i18n: I18nContext) -> str:
    if days % 30 == 0:
        months = days // 30
        return i18n.get("kb-wallet-plan-months", months=months)
    return i18n.get("kb-wallet-plan-days", days=days)


def _get_subscription_menu_text(i18n: I18nContext) -> str:
    return i18n.get("shop-subscription-menu")


def _build_subscription_payload(days: int, *, price_usd_at_creation: float | None = None) -> str:
    data: dict[str, object] = {
        "a": PAYLOAD_ACTION_SUB,
        "d": days,
    }
    if price_usd_at_creation is not None:
        data["u"] = round(float(price_usd_at_creation), 2)
    return orjson.dumps(data).decode("utf-8")


def _build_manual_invoice_external_id(user_id: int) -> str:
    return f"manual_{user_id}_{uuid4().hex[:20]}"


def _build_cactus_invoice_external_id(user_id: int) -> str:
    return f"cactus_{user_id}_{uuid4().hex[:20]}"


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


def _format_card_number(card_number: str) -> str:
    raw = (card_number or "").replace(" ", "")
    return " ".join(raw[i:i + 4] for i in range(0, len(raw), 4)) if raw else (card_number or "")


def _format_cactus_countdown_seconds(seconds_left: int) -> str:
    if seconds_left <= 0:
        return "00:00"
    minutes = seconds_left // 60
    seconds = seconds_left % 60
    return f"{minutes:02d}:{seconds:02d}"


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

    tariff = config.TARIFFS.get(days)
    price_usd = tariff.price_usd if tariff else None
    user_id = callback.from_user.id
    if not price_usd:
        await callback.answer(i18n.get("shop-plan-not-found"), show_alert=True)
        return

    user = await user_service.get_user_by_id(session, user_id)
    if not user:
        await callback.answer(i18n.get("profile-not-found-start"), show_alert=True)
        return

    plan_label = _format_plan_label(days, i18n)
    price_usd = round(float(price_usd), 2)
    current_balance = round(float(user.balance), 2)
    if current_balance >= price_usd:
        text = i18n.get(
            "shop-balance-purchase-confirm",
            balance=hbold(f"{format_smart_num(current_balance)} USDT"),
            plan_label=hbold(plan_label),
            price=hbold(f"{format_smart_num(price_usd)} USDT"),
        )
        await _render_shop_screen(callback, text, get_balance_purchase_confirm_kb(days))
        await callback.answer()
        return

    amount_to_pay = round(price_usd - current_balance, 2)
    payload = _build_subscription_payload(days=days, price_usd_at_creation=amount_to_pay)
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
        price=hbold(f"{format_smart_num(price_usd)} USDT"),
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


async def _start_cactus_payment_flow(
    callback: types.CallbackQuery,
    session: AsyncSession,
    i18n: I18nContext,
    *,
    days: int,
    method: str,
) -> None:
    """
    Стратегия CactusPay Hosted Checkout (ссылка на внешнюю платёжную страницу).

    Поток:
      0. Пер-user Redis-lock (TTL 10s) чтобы предотвратить Order Flooding при
          двойном клике (Race Condition find_active → HTTP create_payment → INSERT).
      1. Balance shortcut — если баланс >= price_usd → экран подтверждения списания.
      2. enabled-проверка cactus_client.
      3. Найти существующий активный PENDING Cactus-инвойс в БД:
            find_active_cactus_invoice(user_id, days=days, amount=amount_to_pay_usd)
         Если найден → переиспользуем, НЕ звоним в API Cactus.
      4. Если нет активного → create_payment(h2h=False — Hosted Mode).
         ВАЖНО:
            • address = payment_url в invoice.address.
            • amount_expected_native = RUB (с clamp ≥ CACTUS_MIN_AMOUNT_RUB = 100 RUB).
            • payload["u"] = amount_to_pay_usd (Price-At-Creation Safety).
      5. Игнорируем блок requisite полностью — используем ТОЛЬКО поле create_resp.url.
      6. Hosted UI + countdown MM:SS + кнопка-ссылка.
    """
    from datetime import datetime, timezone, timedelta

    user_id = callback.from_user.id
    # ------------------------------------------------------------------
    # 0. RACE CONDITION FIX (ISSUE #5): пер-user Redis-lock на create-path.
    #    Без этого double-click → 2 find_active=None → 2 HTTP create_payment → 2 инвойса.
    # ------------------------------------------------------------------
    lock_key = _CREATE_PAYMENT_LOCK_KEY.format(user_id=user_id)
    lock_res, lock_token = await redis_bus.acquire_lock(
        lock_key, ttl=_CREATE_PAYMENT_LOCK_TTL_SEC,
    )
    if lock_res != LockResult.ACQUIRED:
        logger.info(
            "[Cactus._start_cactus_payment_flow] LOCK BUSY user=%s lock=%s → abort (double-click prevented).",
            user_id, lock_key,
        )
        await callback.answer(
            i18n.get("wallet-payment-processing"),  # "⏳ Платеж уже обрабатывается. Подождите пару секунд."
            show_alert=True,
        )
        return
    try:
        tariff = config.TARIFFS.get(days)
        if tariff is None:
            await callback.answer(i18n.get("shop-plan-not-found"), show_alert=True)
            return

        price_usd = round(float(tariff.price_usd), 2)
        price_rub = round(float(tariff.price_rub), 2)
        method = (method or "card").lower()
        if method not in {"card", "sbp"}:
            method = "card"

        user = await user_service.get_user_by_id(session, user_id)
        if not user:
            await callback.answer(i18n.get("profile-not-found-start"), show_alert=True)
            return

        plan_label = _format_plan_label(days, i18n)
        current_balance = round(float(user.balance), 2)

        # 1. Balance shortcut
        if current_balance >= price_usd:
            text = i18n.get(
                "shop-balance-purchase-confirm",
                balance=hbold(f"{format_smart_num(current_balance)} USDT"),
                plan_label=hbold(plan_label),
                price=hbold(f"{format_smart_num(price_usd)} USDT"),
            )
            await _render_shop_screen(callback, text, get_balance_purchase_confirm_kb(days))
            await callback.answer()
            return

        # 2. Cactus enabled check
        if not cactus_client.enabled:
            await callback.answer(i18n.get("shop-cactus-unavailable"), show_alert=True)
            return

        amount_to_pay_usd = round(price_usd - current_balance, 2)
        # Конвертация target→native: прайсинг тарифа фиксированный.
        # Если пользователь оплачивает с доплатой (баланс > 0), native-сумма линейно масштабируется.
        native_amount_rub = price_rub if amount_to_pay_usd >= price_usd else round(
            (amount_to_pay_usd / price_usd) * price_rub,
            2,
        )
        # ------------------------------------------------------------------
        # ISSUE #1 FIX: CACTUS_MIN_AMOUNT_RUB=100.0 clamp.
        # Без этого: balance=24.5 из 25 USD → native=50 RUB < 100 → CactusAPIError,
        # пользователь видит общий "gateway-error" toast без объяснения.
        # Безопасно увеличиваем native_amount_rub до минимума: Delta-Accounting
        # в billing_processor всегда начисляет payload[u]=amount_to_pay_usd (оригинал),
        # так что факт оплаты 100 RUB вместо 50 RUB не меняет USDT-зачисление.
        # ------------------------------------------------------------------
        if native_amount_rub < CACTUS_MIN_AMOUNT_RUB:
            logger.warning(
                "[Cactus._start_cactus_payment_flow] CLAMP native_amount_rub: "
                "user=%s days=%s linear=%.2f RUB clamped_up_to=%.2f RUB (CACTUS_MIN_AMOUNT_RUB); "
                "payload[u]=%.2f USDT остаётся неизменным (Delta-Accounting).",
                user_id, days, native_amount_rub, CACTUS_MIN_AMOUNT_RUB, amount_to_pay_usd,
            )
            native_amount_rub = CACTUS_MIN_AMOUNT_RUB
        description = i18n.get(
            "shop-cactus-description",
            days=days,
        )

        # ================================================================
        # 3. PERSISTENCE: ищем активный (PENDING + expires_at>now, тариф/цена match)
        #    Cactus-инвойс в БД, чтобы избежать лишних create_payment в API.
        # ================================================================
        existing_inv = await billing_service.find_active_cactus_invoice(
            session,
            user_id=user_id,
            days=days,
            amount_to_pay_usd=amount_to_pay_usd,
        )
        if existing_inv is not None:
            # Восстанавливаем URL из address-поля БД, external_id, expires_at, native-суммы.
            external_id = str(existing_inv.external_id)
            payment_url = (existing_inv.address or "").strip() or None
            native_amount_rub = round(float(existing_inv.amount_expected_native or native_amount_rub), 2)
            expires_at = existing_inv.expires_at  # naive UTC, TIMESTAMP WITHOUT TZ
            logger.info(
                "[Cactus._start_cactus_payment_flow] REUSE existing invoice id=%s ext_id=%s user=%s url_set=%s expires_at=%s",
                existing_inv.id, external_id, user_id, bool(payment_url),
                expires_at.isoformat() if expires_at else None,
            )
        else:
            # =============================================================
            # 4. NEW INVOICE: нет активного — создаём API Cactus и запись БД.
            # =============================================================
            external_id = _build_cactus_invoice_external_id(user_id)
            payload = _build_subscription_payload(days=days, price_usd_at_creation=amount_to_pay_usd)

            expires_at = None
            payment_url = None
            try:
                # Hosted Mode: h2h=False → Cactus вернёт URL на hosted checkout-страницу
                # (реквизиты в ответе обычно не приходят, в любом случае — игнорируем их)
                create_resp = await cactus_client.create_payment(
                    amount_rub=native_amount_rub,
                    order_id=external_id,
                    description=description,
                    h2h=False,
                    method=method,
                    user_ip="127.0.0.1",
                )
            except CactusConfigurationError:
                await callback.answer(i18n.get("shop-cactus-unavailable"), show_alert=True)
                return
            except CactusAPIError as exc:
                logger.error(
                    "Cactus create_payment (hosted) error for user %s days=%s method=%s: %s",
                    user_id, days, method, exc,
                )
                await callback.answer(i18n.get("wallet-payment-gateway-error"), show_alert=True)
                return

            # Полный лог всего ответа Cactus (HOSTED). requisite игнорируем, но логируем чтобы
            # в продакшене можно было посмотреть, что прислал шлюз.
            try:
                import orjson as _orjson
                _dump = _orjson.dumps(
                    {
                        "order_id": external_id,
                        "mode": "HOSTED",
                        "method": method,
                        "create_resp_url": create_resp.url,
                        "requisite_keys": list((create_resp.requisite or {}).keys()),
                        "request_check": create_resp.request_check,
                    },
                    option=_orjson.OPT_INDENT_2 | _orjson.OPT_SORT_KEYS,
                ).decode("utf-8", errors="replace")
            except Exception as _log_exc:
                _dump = f"<<< serialize fail: {_log_exc!r} >>> url={create_resp.url!r}"
            logger.info(
                "[Cactus._start_cactus_payment_flow] NEW hosted create_payment user=%s days=%s method=%s dev_mode=%s:\n%s",
                user_id, days, method, getattr(cactus_client, "_dev_mode", None), _dump,
            )

            # Извлекаем expires_at: ИЗ create_resp.requisite.until_timestamp (если есть),
            # иначе из CACTUS_INVOICE_LIFETIME_SEC (fallback, Hosted-режим обычно тоже имеет until).
            requisite = create_resp.requisite or {}
            until_ts_raw = requisite.get("until_timestamp")
            if isinstance(until_ts_raw, (int, float)) and until_ts_raw > 0:
                expires_at = datetime.fromtimestamp(int(until_ts_raw), tz=timezone.utc).replace(tzinfo=None)
            else:
                expires_at = (
                    datetime.now(timezone.utc)
                    + timedelta(seconds=config.CACTUS_INVOICE_LIFETIME_SEC or 480)
                ).replace(tzinfo=None)

            # Извлекаем Payment URL из create_resp.url (единственное поле, которое используем).
            # Важно: DEV_MODE=True mock возвращает https://pay.cactuspay.pro/mock/{uuid} — тоже работает.
            payment_url_raw = create_resp.url or None
            if isinstance(payment_url_raw, str) and payment_url_raw.strip():
                payment_url = payment_url_raw.strip()

            # URL-валидация в реальном режиме (dev_mode=False): если URL невалиден →
            # ошибка юзеру (как и было с реквизитами). В DEV_MODE — OK, даже если URL None.
            _dev_mode_active = bool(getattr(cactus_client, "_dev_mode", False))
            if not _dev_mode_active:
                url_ok = isinstance(payment_url, str) and payment_url.startswith(("http://", "https://"))
                if not url_ok:
                    logger.error(
                        "[Cactus._start_cactus_payment_flow] VALIDATION FAIL: hosted payment URL missing/invalid "
                        "for user=%s order_id=%s url_value=%r",
                        user_id, external_id, payment_url,
                    )
                    await callback.answer(i18n.get("shop-cactus-requisite-error"), show_alert=True)
                    return

            # Запись в БД:
            # • address = payment_url (Persistence Requirement #2: Address Field)
            # • currency="RUB" + amount_expected_native (Data Integrity)
            # • payload["u"] = amount_to_pay_usd → Delta-Accounting защита в billing_processor
            invoice = await billing_service.create_invoice(
                session=session,
                user_id=user_id,
                external_id=external_id,
                amount_expected=amount_to_pay_usd,
                provider=CACTUS_PROVIDER,
                address=payment_url,
                network=None,
                payload=payload,
                currency="RUB",
                amount_expected_native=native_amount_rub,
                amount_actual_native=0.0,
                expires_at=expires_at,
            )
            if invoice is None:
                await callback.answer(i18n.get("wallet-payment-gateway-error"), show_alert=True)
                return

            logger.info(
                "[Cactus._start_cactus_payment_flow] NEW invoice created id=%s ext_id=%s user=%s "
                "amount_usd=%.2f rub=%.2f address_set=%s expires_at=%s",
                invoice.id, external_id, user_id,
                amount_to_pay_usd, native_amount_rub,
                bool(payment_url),
                expires_at.isoformat() if expires_at else None,
            )

        # ================================================================
        # 5. Render Hosted Checkout UI (ignoring requisite completely)
        # ================================================================
        now = datetime.now(timezone.utc)

        # Countdown seconds: expires_at (naive UTC) → до now.
        countdown_seconds: int = int(config.CACTUS_INVOICE_LIFETIME_SEC or 480)
        if expires_at is not None:
            exp_aware = expires_at if expires_at.tzinfo is not None else expires_at.replace(tzinfo=timezone.utc)
            countdown_seconds = max(0, int((exp_aware - now).total_seconds()))
        lifetime_minutes = int(round(int(config.CACTUS_INVOICE_LIFETIME_SEC or 480) / 60))

        invoice_short_id = external_id.split("_")[-1]
        if not invoice_short_id:
            invoice_short_id = external_id[:16]

        text = i18n.get(
            "shop-cactus-pay-hosted-screen",
            plan_label=plan_label,
            invoice_id=hcode(invoice_short_id),
            amount_rub=hbold(f"{format_smart_num(native_amount_rub)} RUB"),
            amount_usd=hbold(f"{format_smart_num(amount_to_pay_usd)} USDT"),
            balance=hbold(f"{format_smart_num(current_balance)} USDT"),
            countdown=hbold(_format_cactus_countdown_seconds(countdown_seconds)),
            lifetime_minutes=str(lifetime_minutes),
        )

        await _render_shop_screen(
            callback,
            text,
            reply_markup=get_cactus_hosted_payment_kb(external_id, payment_url),
            image_path=None,
        )
        await callback.answer()
    finally:
        # ------------------------------------------------------------------
        # Освобождаем Redis-lock даже если внутри возникло исключение / early return.
        # (Иначе пользователь бы заблокировал создание новых Cactus-инвойсов на 10 сек.)
        # ------------------------------------------------------------------
        if lock_res == LockResult.ACQUIRED and lock_token:
            try:
                await redis_bus.release_lock(lock_key, lock_token)
            except Exception as _lock_exc:
                logger.warning(
                    "[Cactus._start_cactus_payment_flow] release_lock FAIL user=%s key=%s err=%s",
                    user_id, lock_key, _lock_exc,
                )


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

    try:
        await callback.message.delete()
    except Exception:
        pass
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
async def callback_process_purchase(
    callback: types.CallbackQuery,
    session: AsyncSession,
    i18n: I18nContext,
):
    """
    Target-Action Flow покупки тарифа.
    Этап 1: если достаточно USDT на балансе — экран подтверждения списания.
    Этап 2: если не хватает — меню выбора метода оплаты (Cactus card, Cactus sbp, Crypto manual).
    """
    try:
        days = int(callback.data.split("_")[2])
    except (ValueError, IndexError):
        return await callback.answer(i18n.get("shop-invalid-plan-params"), show_alert=True)

    tariff = config.TARIFFS.get(days)
    price = tariff.price_usd if tariff else None
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

    # Меню выбора способа оплаты:
    # - Всегда показываем кнопки Cactus (Card/SBP). Если Cactus не сконфигурирован —
    #   при клике пользователь получит toast shop-cactus-unavailable. Это даёт
    #   симметрию UI: текст экрана "рекомендуем карту/СБП" не расходится с кнопками.
    # - Manual Crypto показываем только при наличии кошелька и админ-чата.
    show_cactus = True
    show_manual = bool(config.PAYMENT_MANUAL_WALLET and config.ADMIN_PAYMENT_CHAT_ID)
    if not show_cactus and not show_manual:
        return await callback.answer(i18n.get("shop-no-payment-methods"), show_alert=True)

    amount_to_pay = round(price - current_balance, 2)
    plan_label = _format_plan_label(days, i18n)
    price_rub = round(tariff.price_rub, 2)
    text = i18n.get(
        "shop-payment-method-selection",
        plan_label=hbold(plan_label),
        price_usd=hbold(f"{format_smart_num(price)} USDT"),
        balance=hbold(f"{format_smart_num(current_balance)} USDT"),
        amount_to_pay_usd=hbold(f"{format_smart_num(amount_to_pay)} USDT"),
        price_rub=hbold(f"{format_smart_num(price_rub)} RUB"),
    )
    await _render_shop_screen(
        callback,
        text,
        reply_markup=get_payment_method_selection_kb(
            days,
            show_cactus=show_cactus,
            show_manual=show_manual,
        ),
        image_path=None,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("pay_cactus_"))
async def callback_pay_cactus(callback: types.CallbackQuery, session: AsyncSession, i18n: I18nContext):
    """Запускает Hosted Checkout CactusPay (одна кнопка: Карта РФ / СБП / QR)."""
    try:
        days = int(callback.data.split("_")[2])
    except (ValueError, IndexError):
        return await callback.answer(i18n.get("shop-invalid-plan-params"), show_alert=True)

    await _start_cactus_payment_flow(callback, session, i18n, days=days, method="card")


@router.callback_query(F.data.startswith("cactus_check_"))
async def callback_cactus_check_payment(
    callback: types.CallbackQuery,
    session: AsyncSession,
    i18n: I18nContext,
):
    """Пользователь нажал «Я оплатил» — мгновенный ручной триггер process_payment_update."""
    try:
        external_id = callback.data.split("_", 2)[2]
    except (ValueError, IndexError):
        return await callback.answer(i18n.get("wallet-invalid-invoice-id"), show_alert=True)

    invoice = await billing_service.get_invoice_by_external_id(session, external_id)
    if (
        not invoice
        or invoice.user_id != callback.from_user.id
        or str(invoice.provider or "").upper() != CACTUS_PROVIDER
    ):
        return await callback.answer(i18n.get("wallet-invoice-not-found"), show_alert=True)

    from src.services.logic.billing_processor import process_payment_update
    result = await process_payment_update(session, external_id)

    if result.sub_activated and result.new_end_date:
        purchaser = await user_service.get_user_by_id(session, invoice.user_id)
        referrer_id = purchaser.referrer_id if purchaser else None
        text = i18n.get(
            "shop-purchase-success",
            new_end=hbold(format_datetime(result.new_end_date)),
            price=hbold(f"{format_smart_num(result.amount_actual)} USDT"),
        )
        await _render_shop_screen(
            callback,
            text,
            reply_markup=get_payment_success_kb(),
            image_path=ImagePaths.PAYMENT,
        )
        await invalidate_user_cache(invoice.user_id)
        await _send_referral_bonus_notification(callback, session, referrer_id, result.delta_credited, i18n)
        return await callback.answer(i18n.get("shop-subscription-extended"))

    if result.is_paid:
        # Частичное автоначисление без автоактивации (Price-At-Creation изменился)
        purchaser = await user_service.get_user_by_id(session, invoice.user_id)
        referrer_id = purchaser.referrer_id if purchaser else None
        text = i18n.get(
            "shop-balance-credited-but-auto-activation-skipped",
            balance=hbold(f"{format_smart_num(result.new_balance)} USDT"),
            needed=hbold(f"{format_smart_num(result.needed_amount)} USDT"),
        )
        await _render_shop_screen(callback, text, get_payment_success_kb())
        await invalidate_user_cache(invoice.user_id)
        await _send_referral_bonus_notification(callback, session, referrer_id, result.delta_credited, i18n)
        return await callback.answer(i18n.get("wallet-balance-paid-success-screen"))

    if result.invoice_status == "EXPIRED":
        await callback.answer(i18n.get("shop-cactus-expired"), show_alert=True)
        return

    if result.invoice_status == "PARTIAL":
        await callback.answer(i18n.get("wallet-payment-partial-toast"), show_alert=True)
        return

    await callback.answer(i18n.get("shop-cactus-wait-processing"), show_alert=True)


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

    tariff = config.TARIFFS.get(days)
    price = tariff.price_usd if tariff else None
    user_id = callback.from_user.id
    if not price:
        return await callback.answer(i18n.get("shop-plan-not-found"), show_alert=True)

    success, new_end, bonus_amount = await billing_service.purchase_subscription(session, user_id, days, price)
    if not success or not new_end:
        return await callback.answer(i18n.get("shop-insufficient-balance"), show_alert=True)
        
    await invalidate_user_cache(user_id)
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
