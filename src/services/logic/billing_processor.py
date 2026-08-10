import json
import logging
import re

import orjson
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import config
from src.core.dto import PaymentUpdateDTO
from src.core.redis_bus import LockResult, redis_bus
from src.database.crud import billing_service
from src.database.models import Invoice, Transaction, UserEvent
from src.services.analyzer import invalidate_user_cache
from src.services.cactus_client import CactusAPIError, cactus_client
from src.services.cryptomus import CryptomusAPIError, cryptomus_client
from src.services.cryptopay import cryptopay

logger = logging.getLogger(__name__)

EXPIRED_PROVIDER_STATUSES = {"expired", "cancel", "cancelled", "deleted", "fail", "system_fail"}
PAYMENT_LOCK_TTL_SEC = 15
LEGACY_SUB_PAYLOAD_RE = re.compile(r"sub_(\d+)")
MANUAL_PAYMENT_PROVIDER = "MANUAL"
CACTUS_PROVIDER = "CACTUS"
CACTUS_SUCCESS_STATUS = "ACCEPT"


def _round_money(value: float | int | None) -> float:
    if value is None:
        return 0.0
    return round(float(value), 2)


def _build_user_payment_lock_key(user_id: int) -> str:
    return f"csl:lock:payment:user:{user_id}"


def _parse_invoice_intent(payload: str | None) -> tuple[str | None, int | None]:
    if not payload:
        return None, None

    raw_payload = payload.strip()
    if not raw_payload:
        return None, None

    try:
        loaded = orjson.loads(raw_payload)
    except orjson.JSONDecodeError:
        try:
            loaded = json.loads(raw_payload)
        except json.JSONDecodeError:
            loaded = None

    if isinstance(loaded, dict):
        action = str(loaded.get("a") or "").strip().lower() or None
        days_raw = loaded.get("d")
        try:
            days = int(days_raw) if days_raw is not None else None
        except (TypeError, ValueError):
            days = None
        return action, days

    legacy_match = LEGACY_SUB_PAYLOAD_RE.search(raw_payload)
    if legacy_match:
        return "sub", int(legacy_match.group(1))

    return None, None


def _extract_price_at_creation_usd(payload: str | None) -> float | None:
    """
    Safety: Возвращает цену тарифа в USDT, зафиксированную в момент создания инвойса.
    Используется для CactusPay, чтобы избежать drift'a цены в `config.TARIFFS` между созданием
    инвойса и подтверждением платежа. Поле в payload: `u` (цена в USDT на момент создания).
    """
    if not payload:
        return None
    raw_payload = payload.strip()
    if not raw_payload:
        return None
    try:
        loaded = orjson.loads(raw_payload)
    except orjson.JSONDecodeError:
        try:
            loaded = json.loads(raw_payload)
        except json.JSONDecodeError:
            return None
    if not isinstance(loaded, dict):
        return None
    price_raw = loaded.get("u")
    if price_raw is None:
        return None
    try:
        return _round_money(price_raw)
    except (TypeError, ValueError):
        return None


def _resolve_invoice_status(provider_status: str, amount_actual: float, amount_expected: float) -> str:
    normalized_status = (provider_status or "").strip().lower()
    if normalized_status in EXPIRED_PROVIDER_STATUSES and amount_actual <= 0:
        return "EXPIRED"
    if amount_actual >= amount_expected and amount_actual > 0:
        return "PAID"
    if amount_actual > 0:
        return "PARTIAL"
    return "PENDING"


async def _get_provider_payment_snapshot(invoice: Invoice) -> tuple[str, float, float]:
    """
    Возвращает `(provider_status_normalized, credited_amount_usdt, actual_native_amount)`.

    Для CRYPTOMUS/CRYPTOPAY `credited_amount_usdt` == фактической сумме в USDT от провайдера.
    Для CACTUS (RUB → USDT): `credited_amount_usdt` фиксируется из `payload['u']`
    (цена тарифа на момент создания инвойса), а `actual_native_amount` — сколько реально
    пришло RUB (нужен только для отображения в журнале).
    """
    provider = (invoice.provider or "CRYPTOMUS").upper()

    if provider == "CRYPTOMUS":
        response = await cryptomus_client.get_status(uuid=invoice.external_id)
        native = _round_money(response.payment_amount)
        return (response.status or response.payment_status or "unknown").lower(), native, native

    if provider == "CRYPTOPAY":
        status = await cryptopay.check_invoice_status(int(invoice.external_id))
        normalized_status = (status or "unknown").lower()
        amount_actual = invoice.amount_actual
        if normalized_status == "paid":
            amount_actual = invoice.amount_expected
        native = _round_money(amount_actual)
        return normalized_status, native, native

    if provider == CACTUS_PROVIDER:
        response = await cactus_client.get_status(order_id=invoice.external_id)
        provider_status = str(response.status or "WAIT").lower()

        if provider_status == CACTUS_SUCCESS_STATUS.lower():
            price_at_creation_usd = _extract_price_at_creation_usd(invoice.payload)
            if price_at_creation_usd is None or price_at_creation_usd <= 0:
                _, intent_days = _parse_invoice_intent(invoice.payload)
                tariff = config.TARIFFS.get(intent_days) if intent_days else None
                fallback = _round_money(tariff.price_usd if tariff else None)
                target_usdt = fallback if fallback > 0 else _round_money(invoice.amount_expected)
            else:
                target_usdt = price_at_creation_usd
            actual_native_rub = _round_money(response.total_amount)
            return "paid", target_usdt, actual_native_rub

        return provider_status, 0.0, 0.0

    raise ValueError(f"Unsupported payment provider: {provider}")


async def _get_invoice_credited_total(
    session: AsyncSession,
    user_id: int,
    external_id: str,
) -> float:
    result = await session.execute(
        select(func.sum(Transaction.amount)).where(
            Transaction.user_id == user_id,
            Transaction.type == "DEPOSIT",
            Transaction.description.like(f"%Invoice #{external_id}%"),
        )
    )
    return _round_money(result.scalar() or 0.0)


async def _has_subscription_charge_for_invoice(
    session: AsyncSession,
    user_id: int,
    external_id: str,
) -> bool:
    result = await session.execute(
        select(Transaction.id).where(
            Transaction.user_id == user_id,
            Transaction.type == "WITHDRAW",
            Transaction.description == f"Direct Pay subscription via Invoice #{external_id}",
        )
    )
    return result.scalar_one_or_none() is not None


def _resolve_effective_paid_amount(provider_amount: float, amount_expected: float) -> float:
    actual_amount = _round_money(provider_amount)
    shortfall = _round_money(amount_expected - actual_amount)
    if 0 < shortfall <= _round_money(config.PAYMENT_TOLERANCE_USD):
        return amount_expected
    return actual_amount


async def process_manual_approval(
    session: AsyncSession,
    ext_id: str,
    admin_id: int,
    amount_actual: float,
    admin_name: str | None = None,
) -> PaymentUpdateDTO:
    """
    Применяет ручное подтверждение оплаты от администратора как внешний
    платежный snapshot для инвойсов провайдера `MANUAL`.
    """
    approved_amount = _round_money(amount_actual)
    if approved_amount <= 0:
        return PaymentUpdateDTO(
            is_paid=False,
            delta_credited=0.0,
            sub_activated=False,
            new_balance=0.0,
            new_end_date=None,
            error="invalid_manual_amount",
            admin_name=admin_name,
        )

    invoice_snapshot = await billing_service.get_invoice_by_external_id(session, ext_id)
    if invoice_snapshot is None:
        return PaymentUpdateDTO(
            is_paid=False,
            delta_credited=0.0,
            sub_activated=False,
            new_balance=0.0,
            new_end_date=None,
            error="invoice_not_found",
            admin_name=admin_name,
            invoice_status="NOT_FOUND",
        )

    snapshot_user_id = int(invoice_snapshot.user_id)
    snapshot_amount_actual = _round_money(invoice_snapshot.amount_actual)
    snapshot_amount_expected = _round_money(invoice_snapshot.amount_expected)
    snapshot_status = str(invoice_snapshot.status)

    await session.rollback()

    lock_token: str | None = None
    lock_result, lock_token = await redis_bus.acquire_lock(
        _build_user_payment_lock_key(snapshot_user_id),
        ttl=PAYMENT_LOCK_TTL_SEC,
    )
    if lock_result is LockResult.ERROR:
        return PaymentUpdateDTO(
            is_paid=False,
            delta_credited=0.0,
            sub_activated=False,
            new_balance=0.0,
            new_end_date=None,
            error="lock_error",
            admin_name=admin_name,
            amount_actual=snapshot_amount_actual,
            amount_expected=snapshot_amount_expected,
            invoice_status=snapshot_status,
        )
    if lock_result is LockResult.BUSY:
        return PaymentUpdateDTO(
            is_paid=False,
            delta_credited=0.0,
            sub_activated=False,
            new_balance=0.0,
            new_end_date=None,
            error="payment_processing",
            admin_name=admin_name,
            amount_actual=snapshot_amount_actual,
            amount_expected=snapshot_amount_expected,
            invoice_status=snapshot_status,
        )

    cache_invalidation_needed = False
    dto = PaymentUpdateDTO(
        is_paid=False,
        delta_credited=0.0,
        sub_activated=False,
        new_balance=0.0,
        new_end_date=None,
        error=None,
        admin_name=admin_name,
    )

    try:
        async with session.begin():
            invoice, user = await billing_service.get_billing_entities(session, ext_id)
            if invoice is None:
                dto.error = "invoice_not_found"
                dto.invoice_status = "NOT_FOUND"
                return dto
            if user is None:
                dto.error = "user_not_found"
                dto.invoice_status = invoice.status
                dto.amount_actual = _round_money(invoice.amount_actual)
                dto.amount_expected = _round_money(invoice.amount_expected)
                return dto

            if (invoice.provider or "").upper() != MANUAL_PAYMENT_PROVIDER:
                dto.error = "manual_provider_mismatch"
                dto.invoice_status = invoice.status
                dto.amount_actual = _round_money(invoice.amount_actual)
                dto.amount_expected = _round_money(invoice.amount_expected)
                dto.new_balance = _round_money(user.balance)
                return dto

            intent_action, intent_days = _parse_invoice_intent(invoice.payload)
            amount_expected = _round_money(invoice.amount_expected)
            dto.amount_expected = amount_expected
            dto.amount_actual = _round_money(invoice.amount_actual)
            dto.invoice_status = invoice.status
            dto.intent_action = intent_action
            dto.intent_days = intent_days
            dto.needed_amount = max(_round_money(amount_expected - dto.amount_actual), 0.0)
            dto.new_balance = _round_money(user.balance)

            original_status = invoice.status
            original_amount_actual = _round_money(invoice.amount_actual)
            if original_status == "PAID" and approved_amount <= original_amount_actual:
                dto.is_paid = True
                dto.needed_amount = 0.0
                if intent_action == "sub" and intent_days:
                    already_charged = await _has_subscription_charge_for_invoice(
                        session=session,
                        user_id=user.id,
                        external_id=invoice.external_id,
                    )
                    if already_charged:
                        dto.sub_activated = True
                        dto.new_end_date = user.subscription_end
                return dto

            resolved_amount_actual = max(approved_amount, original_amount_actual)
            effective_paid_amount = _resolve_effective_paid_amount(
                provider_amount=resolved_amount_actual,
                amount_expected=amount_expected,
            )
            credited_total = await _get_invoice_credited_total(
                session=session,
                user_id=user.id,
                external_id=invoice.external_id,
            )
            delta = _round_money(effective_paid_amount - credited_total)
            target_status = _resolve_invoice_status("manual", effective_paid_amount, amount_expected)

            dto.amount_actual = resolved_amount_actual
            dto.invoice_status = target_status
            dto.needed_amount = max(_round_money(amount_expected - effective_paid_amount), 0.0)

            if delta > 0:
                new_balance = await billing_service.adjust_user_balance(
                    session=session,
                    user_id=user.id,
                    amount=delta,
                    tx_type="DEPOSIT",
                    description=(
                        f"Пополнение через {MANUAL_PAYMENT_PROVIDER} "
                        f"(Invoice #{invoice.external_id}, approved_by={admin_id})"
                    ),
                )
                if new_balance is None:
                    dto.error = "user_not_found"
                    return dto
                dto.delta_credited = delta
                dto.new_balance = new_balance
                cache_invalidation_needed = True

            updated_invoice = await billing_service.update_invoice_record(
                session=session,
                invoice_id=invoice.id,
                amount_actual=resolved_amount_actual,
                status=target_status,
            )
            if updated_invoice is None:
                dto.error = "invoice_not_found"
                dto.invoice_status = "NOT_FOUND"
                return dto

            reviewed_invoice = await billing_service.update_invoice_review_metadata(
                session=session,
                invoice_id=invoice.id,
                approved_by_admin_id=admin_id,
                screenshot_file_id=invoice.screenshot_file_id,
                rejection_reason=None,
            )
            if reviewed_invoice is None:
                dto.error = "invoice_not_found"
                dto.invoice_status = "NOT_FOUND"
                return dto

            admin_actor = (admin_name or f"id={admin_id}").strip()
            event_payload = (
                f"manual_approval:{invoice.external_id}:"
                f"{format(_round_money(approved_amount), '.2f')}:"
                f"{target_status}:{admin_actor}"
            )[:255]
            session.add(
                UserEvent(
                    user_id=user.id,
                    event_type="manual_payment_review",
                    event_data=event_payload,
                    is_admin=True,
                )
            )

            if target_status == "PAID" and intent_action == "sub" and intent_days:
                already_charged = await _has_subscription_charge_for_invoice(
                    session=session,
                    user_id=user.id,
                    external_id=invoice.external_id,
                )
                if already_charged:
                    dto.sub_activated = True
                    dto.new_end_date = user.subscription_end
                else:
                    tariff = config.TARIFFS.get(intent_days)
                    subscription_price = _round_money(tariff.price_usd if tariff else None)
                    if subscription_price <= 0:
                        dto.error = "subscription_price_not_found"
                    elif dto.new_balance < subscription_price:
                        dto.needed_amount = max(_round_money(subscription_price - dto.new_balance), 0.0)
                        dto.error = "insufficient_balance_for_intent"
                    else:
                        new_end_date = await billing_service.extend_user_subscription(
                            session=session,
                            user_id=user.id,
                            days=intent_days,
                        )
                        if new_end_date is None:
                            dto.error = "user_not_found"
                            return dto

                        new_balance = await billing_service.adjust_user_balance(
                            session=session,
                            user_id=user.id,
                            amount=-subscription_price,
                            tx_type="WITHDRAW",
                            description=f"Direct Pay subscription via Invoice #{invoice.external_id}",
                        )
                        if new_balance is None:
                            dto.error = "user_not_found"
                            return dto

                        dto.sub_activated = True
                        dto.new_end_date = new_end_date
                        dto.new_balance = new_balance
                        cache_invalidation_needed = True

            dto.is_paid = target_status == "PAID"
            if dto.error is None:
                if target_status == "PARTIAL":
                    dto.error = "partial_payment"
                elif target_status == "PENDING":
                    dto.error = "payment_pending"

            if original_status != target_status:
                cache_invalidation_needed = True

        if cache_invalidation_needed:
            try:
                await invalidate_user_cache(snapshot_user_id)
            except Exception:
                logger.exception(
                    "Не удалось инвалидировать кеш пользователя после ручного подтверждения user_id=%s",
                    snapshot_user_id,
                )
        return dto
    except Exception:
        logger.exception("Не удалось обработать ручное подтверждение ext_id=%s", ext_id)
        await session.rollback()
        return PaymentUpdateDTO(
            is_paid=False,
            delta_credited=0.0,
            sub_activated=False,
            new_balance=0.0,
            new_end_date=None,
            error="unexpected_error",
            amount_actual=snapshot_amount_actual,
            amount_expected=snapshot_amount_expected,
            invoice_status=snapshot_status,
        )
    finally:
        if lock_token is not None:
            await redis_bus.release_lock(_build_user_payment_lock_key(snapshot_user_id), lock_token)


async def process_payment_update(session: AsyncSession, ext_id: str) -> PaymentUpdateDTO:
    """
    Выполняет сетевую синхронизацию платежа вне транзакции и применяет изменения
    к БД внутри одного атомарного блока.
    """
    invoice_snapshot = await billing_service.get_invoice_by_external_id(session, ext_id)
    if invoice_snapshot is None:
        return PaymentUpdateDTO(
            is_paid=False,
            delta_credited=0.0,
            sub_activated=False,
            new_balance=0.0,
            new_end_date=None,
            error="invoice_not_found",
            invoice_status="NOT_FOUND",
        )

    snapshot_user_id = int(invoice_snapshot.user_id)
    snapshot_amount_actual = _round_money(invoice_snapshot.amount_actual)
    snapshot_amount_expected = _round_money(invoice_snapshot.amount_expected)
    snapshot_status = str(invoice_snapshot.status)

    try:
        provider_status, api_amount, actual_native = await _get_provider_payment_snapshot(invoice_snapshot)
    except (CryptomusAPIError, CactusAPIError, ValueError, RuntimeError) as exc:
        logger.error("Ошибка провайдера при проверке ext_id=%s: %s", ext_id, exc)
        return PaymentUpdateDTO(
            is_paid=False,
            delta_credited=0.0,
            sub_activated=False,
            new_balance=0.0,
            new_end_date=None,
            error="provider_error",
            amount_actual=snapshot_amount_actual,
            amount_expected=snapshot_amount_expected,
            invoice_status=snapshot_status,
        )

    await session.rollback()

    lock_token: str | None = None
    lock_result, lock_token = await redis_bus.acquire_lock(
        _build_user_payment_lock_key(snapshot_user_id),
        ttl=PAYMENT_LOCK_TTL_SEC,
    )
    if lock_result is LockResult.ERROR:
        return PaymentUpdateDTO(
            is_paid=False,
            delta_credited=0.0,
            sub_activated=False,
            new_balance=0.0,
            new_end_date=None,
            error="lock_error",
            amount_actual=snapshot_amount_actual,
            amount_expected=snapshot_amount_expected,
            invoice_status=snapshot_status,
        )
    if lock_result is LockResult.BUSY:
        return PaymentUpdateDTO(
            is_paid=False,
            delta_credited=0.0,
            sub_activated=False,
            new_balance=0.0,
            new_end_date=None,
            error="payment_processing",
            amount_actual=snapshot_amount_actual,
            amount_expected=snapshot_amount_expected,
            invoice_status=snapshot_status,
        )

    cache_invalidation_needed = False
    dto = PaymentUpdateDTO(
        is_paid=False,
        delta_credited=0.0,
        sub_activated=False,
        new_balance=0.0,
        new_end_date=None,
        error=None,
    )

    try:
        async with session.begin():
            invoice, user = await billing_service.get_billing_entities(session, ext_id)
            if invoice is None:
                dto.error = "invoice_not_found"
                dto.invoice_status = "NOT_FOUND"
                return dto
            if user is None:
                dto.error = "user_not_found"
                dto.invoice_status = invoice.status
                dto.amount_actual = _round_money(invoice.amount_actual)
                dto.amount_expected = _round_money(invoice.amount_expected)
                return dto

            original_status = invoice.status
            original_amount_actual = _round_money(invoice.amount_actual)
            amount_expected = _round_money(invoice.amount_expected)
            provider_name = (invoice.provider or "CRYPTOMUS").upper()

            if provider_name == CACTUS_PROVIDER:
                # Binary Success: Данные из API допускаются в систему ТОЛЬКО при status=ACCEPT.
                # При WAIT/EXPIRED snapshot уже вернул api_amount=0, actual_native=0 → записи в БД нет.
                effective_paid_amount = _round_money(api_amount)
                resolved_amount_actual = effective_paid_amount
            else:
                resolved_amount_actual = max(_round_money(api_amount), original_amount_actual)
                effective_paid_amount = _resolve_effective_paid_amount(
                    provider_amount=resolved_amount_actual,
                    amount_expected=amount_expected,
                )

            credited_total = await _get_invoice_credited_total(
                session=session,
                user_id=user.id,
                external_id=invoice.external_id,
            )
            delta = _round_money(effective_paid_amount - credited_total)
            target_status = _resolve_invoice_status(provider_status, effective_paid_amount, amount_expected)
            intent_action, intent_days = _parse_invoice_intent(invoice.payload)

            dto.amount_expected = amount_expected
            dto.amount_actual = resolved_amount_actual
            dto.invoice_status = target_status
            dto.intent_action = intent_action
            dto.intent_days = intent_days
            dto.needed_amount = max(_round_money(amount_expected - effective_paid_amount), 0.0)
            dto.new_balance = _round_money(user.balance)

            update_invoice_kwargs: dict = {
                "session": session,
                "invoice_id": invoice.id,
                "amount_actual": resolved_amount_actual,
                "status": target_status,
            }
            if provider_name == CACTUS_PROVIDER and actual_native is not None:
                update_invoice_kwargs["amount_actual_native"] = actual_native

            if delta > 0:
                new_balance = await billing_service.adjust_user_balance(
                    session=session,
                    user_id=user.id,
                    amount=delta,
                    tx_type="DEPOSIT",
                    description=f"Пополнение через {invoice.provider} (Invoice #{invoice.external_id}, status={provider_status})",
                )
                if new_balance is None:
                    dto.error = "user_not_found"
                    return dto
                dto.delta_credited = delta
                dto.new_balance = new_balance
                cache_invalidation_needed = True

            updated_invoice = await billing_service.update_invoice_record(**update_invoice_kwargs)
            if updated_invoice is None:
                dto.error = "invoice_not_found"
                dto.invoice_status = "NOT_FOUND"
                return dto

            if target_status == "PAID" and intent_action == "sub" and intent_days:
                already_charged = await _has_subscription_charge_for_invoice(
                    session=session,
                    user_id=user.id,
                    external_id=invoice.external_id,
                )
                if already_charged:
                    dto.sub_activated = True
                    dto.new_end_date = user.subscription_end
                else:
                    tariff = config.TARIFFS.get(intent_days)
                    subscription_price = _round_money(tariff.price_usd if tariff else None)
                    if subscription_price <= 0:
                        dto.error = "subscription_price_not_found"
                    elif dto.new_balance < subscription_price:
                        dto.needed_amount = max(_round_money(subscription_price - dto.new_balance), 0.0)
                        dto.error = "insufficient_balance_for_intent"
                    else:
                        new_end_date = await billing_service.extend_user_subscription(
                            session=session,
                            user_id=user.id,
                            days=intent_days,
                        )
                        if new_end_date is None:
                            dto.error = "user_not_found"
                            return dto

                        new_balance = await billing_service.adjust_user_balance(
                            session=session,
                            user_id=user.id,
                            amount=-subscription_price,
                            tx_type="WITHDRAW",
                            description=f"Direct Pay subscription via Invoice #{invoice.external_id}",
                        )
                        if new_balance is None:
                            dto.error = "user_not_found"
                            return dto

                        dto.sub_activated = True
                        dto.new_end_date = new_end_date
                        dto.new_balance = new_balance
                        cache_invalidation_needed = True

            dto.is_paid = target_status == "PAID"
            if dto.error is None:
                if target_status == "EXPIRED":
                    dto.error = "invoice_expired"
                elif target_status == "PARTIAL":
                    dto.error = "partial_payment"
                elif target_status == "PENDING":
                    dto.error = "payment_pending"

            if original_status != target_status:
                cache_invalidation_needed = True

        if cache_invalidation_needed:
            try:
                await invalidate_user_cache(snapshot_user_id)
            except Exception:
                logger.exception(
                    "Не удалось инвалидировать кеш пользователя после обработки платежа user_id=%s",
                    snapshot_user_id,
                )
        return dto
    except Exception:
        logger.exception("Не удалось обработать обновление платежа ext_id=%s", ext_id)
        await session.rollback()
        return PaymentUpdateDTO(
            is_paid=False,
            delta_credited=0.0,
            sub_activated=False,
            new_balance=0.0,
            new_end_date=None,
            error="unexpected_error",
            amount_actual=snapshot_amount_actual,
            amount_expected=snapshot_amount_expected,
            invoice_status=snapshot_status,
        )
    finally:
        if lock_token is not None:
            await redis_bus.release_lock(_build_user_payment_lock_key(snapshot_user_id), lock_token)
