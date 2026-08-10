import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import desc, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

import orjson

from src.core.config import config
from src.core.i18n_runtime import background_i18n
from src.core.localization import SUPPORTED_LOCALES
from src.database.functions import get_utc_now
from src.database.models import Invoice, Transaction, User
from src.services.analyzer import invalidate_user_cache

logger = logging.getLogger(__name__)

DEFAULT_PAYMENT_PROVIDER = "CRYPTOMUS"


def _round_money(value: float | int | None) -> float:
    if value is None:
        return 0.0
    return round(float(value), 2)


def _build_bonus_description(internal_description: str, hours: int, locale: str | None) -> str:
    days: int | float = hours // 24 if hours % 24 == 0 else round(hours / 24, 2)
    return background_i18n.get(
        internal_description,
        locale=locale,
        hours=hours,
        days=days,
    )


async def _issue_bonus_subscription_to_user(
    session: AsyncSession,
    user: User,
    *,
    hours: int,
    internal_description: str,
    locale: str | None,
) -> datetime:
    now = get_utc_now()
    current_end = user.subscription_end if user.subscription_end and user.subscription_end > now else now
    new_end = current_end + timedelta(hours=hours)
    user.subscription_end = new_end

    session.add(
        Transaction(
            user_id=user.id,
            amount=0.0,
            type="BONUS",
            description=_build_bonus_description(internal_description, hours, locale),
        )
    )

    await invalidate_user_cache(user.id)
    return new_end


async def issue_bonus_subscription(
    session: AsyncSession,
    user_id: int,
    hours: int,
    internal_description: str,
    locale: str | None,
) -> tuple[bool, datetime | None]:
    """
    Начисляет бонусный период и создает нулевую транзакцию в истории.
    Не делает session.commit().
    """
    try:
        user = await session.get(User, user_id, with_for_update=True)
        if user is None:
            logger.error("Пользователь %s не найден для бонусного начисления", user_id)
            return False, None

        new_end = await _issue_bonus_subscription_to_user(
            session,
            user,
            hours=hours,
            internal_description=internal_description,
            locale=locale,
        )
        return True, new_end
    except Exception as e:
        logger.error("Ошибка в issue_bonus_subscription для %s: %s", user_id, e)
        return False, None


async def apply_community_bonus(
    session: AsyncSession,
    user_id: int,
) -> tuple[bool, datetime | None]:
    """
    Начисляет бонус за вступление в сообщество один раз на пользователя.
    Не делает session.commit().
    """
    try:
        user = await session.get(User, user_id, with_for_update=True)
        if user is None:
            logger.error("Пользователь %s не найден для Community Bonus", user_id)
            return False, None

        if user.is_community_bonus_used:
            logger.info("Community Bonus уже был использован пользователем %s", user_id)
            return False, None

        user.is_community_bonus_used = True
        new_end = await _issue_bonus_subscription_to_user(
            session,
            user,
            hours=config.COMMUNITY_BONUS_HOURS,
            internal_description="billing-tx-community-bonus-description",
            locale=user.language_code,
        )
        return True, new_end
    except Exception as e:
        logger.error("Ошибка в apply_community_bonus для %s: %s", user_id, e)
        return False, None


async def has_active_trial_bonus(session: AsyncSession, user: User) -> bool:
    if not user.subscription_end or not user.is_trial_used:
        return False

    trial_hours = config.TRIAL_DURATION_DAYS * 24
    trial_descriptions = tuple(
        _build_bonus_description("billing-tx-trial-description", trial_hours, locale)
        for locale in SUPPORTED_LOCALES
    )
    result = await session.execute(
        select(Transaction)
        .where(
            Transaction.user_id == user.id,
            Transaction.type == "BONUS",
            Transaction.amount == 0,
            Transaction.description.in_(trial_descriptions),
        )
        .order_by(Transaction.created_at.desc())
        .limit(1)
    )
    trial_tx = result.scalar_one_or_none()
    if trial_tx is None:
        return False

    expected_trial_end = trial_tx.created_at + timedelta(hours=trial_hours)
    return abs((user.subscription_end - expected_trial_end).total_seconds()) <= 300

async def create_invoice(
    session: AsyncSession,
    user_id: int,
    external_id: str,
    amount_expected: float,
    payload: str | None = None,
    *,
    provider: str = DEFAULT_PAYMENT_PROVIDER,
    address: str | None = None,
    network: str | None = None,
    amount_actual: float = 0.0,
    currency: str = "USD",
    amount_expected_native: float = 0.0,
    amount_actual_native: float = 0.0,
    expires_at: datetime | None = None,
) -> Invoice | None:
    """
    Создает новый инвойс для оплаты.
    
    :param session: Асинхронная сессия SQLAlchemy
    :param user_id: ID пользователя
    :param external_id: Внешний ID провайдера
    :param amount_expected: Ожидаемая сумма инвойса в USDT (целевой тариф)
    :param payload: Дополнительная информация (например, 'sub_30' или JSON с ценой создания)
    :param currency: Код валюты native-полей (USD / RUB)
    :param amount_expected_native: Ожидаемая сумма в валюте провайдера (например, 2500 RUB)
    :param amount_actual_native: Фактически оплаченная сумма в native
    :param expires_at: Время истечения реквизитов (H2H-карты)
    :return: Объект Invoice или None при ошибке
    """
    try:
        rounded_amount_expected = round(float(amount_expected), 2)
        # Safety: при создании инвойса фактическая оплата ВСЕГДА равна 0.
        # Игнорируем любые значения, переданные извне (defense-in-depth).
        rounded_amount_actual = 0.0
        rounded_amount_expected_native = round(float(amount_expected_native), 2)
        rounded_amount_actual_native = 0.0
        # Defense-in-depth: колонка expires_at в БД — TIMESTAMP WITHOUT TIME ZONE (naive UTC).
        # Если передан offset-aware datetime — снимаем tzinfo, предполагая UTC.
        normalized_expires_at = expires_at
        if normalized_expires_at is not None and normalized_expires_at.tzinfo is not None:
            normalized_expires_at = normalized_expires_at.astimezone(tz=timezone.utc).replace(tzinfo=None)
        invoice = Invoice(
            user_id=user_id,
            external_id=str(external_id),
            provider=provider,
            address=address,
            network=network,
            amount_expected=rounded_amount_expected,
            amount_actual=rounded_amount_actual,
            status='PENDING',
            payload=payload,
            currency=str(currency or "USD"),
            amount_expected_native=rounded_amount_expected_native,
            amount_actual_native=rounded_amount_actual_native,
            expires_at=normalized_expires_at,
        )
        session.add(invoice)
        await session.commit()
        logger.info(
            "Создан инвойс %s provider=%s currency=%s для пользователя %s: target=%s USDT native_expected=%s (payload=%s)",
            external_id,
            provider,
            invoice.currency,
            user_id,
            rounded_amount_expected,
            rounded_amount_expected_native,
            payload,
        )
        return invoice
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"Ошибка БД в create_invoice для {user_id}: {e}")
        return None
    except Exception as e:
        await session.rollback()
        logger.error(f"Непредвиденная ошибка в create_invoice для {user_id}: {e}")
        return None

async def get_invoice_by_external_id(session: AsyncSession, ext_id: str) -> Invoice | None:
    """Ищет инвойс по внешнему идентификатору без загрузки связей."""
    try:
        invoice_id = await session.scalar(
            select(Invoice.id).where(Invoice.external_id == ext_id)
        )
        if invoice_id is None:
            return None
        return await session.get(Invoice, invoice_id)
    except SQLAlchemyError as e:
        logger.error("Ошибка БД в get_invoice_by_external_id %s: %s", ext_id, e)
        return None
    except Exception as e:
        logger.error("Непредвиденная ошибка в get_invoice_by_external_id %s: %s", ext_id, e)
        return None


async def find_active_cactus_invoice(
    session: AsyncSession,
    user_id: int,
    *,
    days: int,
    amount_to_pay_usd: float,
) -> Invoice | None:
    """
    Ищет активный (неистёкший, PENDING) Cactus-инвойс для переиспользования,
    чтобы не создавать новый платёж в API на ту же сумму/тариф.

    Условия совпадения:
      - provider == 'CACTUS'
      - status == 'PENDING'
      - expires_at is not None AND expires_at > get_utc_now()
      - payload is valid JSON with:
          "a" == "sub" (intent = subscription)
          "d" == days (тот же тариф, дней)
          "u" == round(amount_to_pay_usd, 2)  (Price-At-Creation Safety, та же цена)

    Возвращает самый свежий подходящий инвойс (ORDER BY created_at DESC).
    Если ни одного не найдено — None (нужно создавать новый).
    """
    expected_amount_u = round(float(amount_to_pay_usd), 2)
    try:
        stmt = (
            select(Invoice)
            .where(
                Invoice.user_id == int(user_id),
                (Invoice.provider == "CACTUS") | (Invoice.provider == "cactus"),
                Invoice.status == "PENDING",
                Invoice.expires_at.is_not(None),
            )
            .order_by(desc(Invoice.created_at))
            .limit(20)
        )
        result = await session.execute(stmt)
        candidates = result.scalars().all()

        now = get_utc_now()
        for inv in candidates:
            # expires_at in DB = naive UTC (per column TIMESTAMP WITHOUT TIME ZONE)
            exp = inv.expires_at
            if exp is None:
                continue
            if exp.tzinfo is not None:
                exp = exp.astimezone(tz=timezone.utc).replace(tzinfo=None)
            if exp <= now:
                continue

            # parse payload JSON → must match days and amount_to_pay_usd
            if not inv.payload:
                continue
            try:
                p = orjson.loads(inv.payload)
            except Exception:
                logger.warning(
                    "find_active_cactus_invoice: skip invoice #%s (invalid payload: %r)",
                    inv.id, inv.payload[:80] if isinstance(inv.payload, str) else type(inv.payload).__name__,
                )
                continue

            if not isinstance(p, dict):
                continue
            if str(p.get("a")) != "sub":
                continue
            p_days = p.get("d")
            if not isinstance(p_days, int) or int(p_days) != int(days):
                continue
            p_u = p.get("u")
            try:
                inv_amount_u = round(float(p_u), 2)
            except Exception:
                continue
            if inv_amount_u != expected_amount_u:
                continue

            # All conditions match → reuse this invoice
            logger.info(
                "find_active_cactus_invoice: REUSE invoice id=%s ext_id=%s user=%s days=%s u=%.2f USD expires_at=%s",
                inv.id, inv.external_id, user_id, days, expected_amount_u, exp.isoformat(),
            )
            return inv

        logger.info(
            "find_active_cactus_invoice: NO MATCH user=%s days=%s u=%.2f USD candidates_checked=%d",
            user_id, days, expected_amount_u, len(candidates),
        )
        return None

    except SQLAlchemyError as e:
        logger.error("Ошибка БД в find_active_cactus_invoice user=%s days=%s: %s", user_id, days, e)
        return None
    except Exception as e:
        logger.error("Непредвиденная ошибка в find_active_cactus_invoice user=%s days=%s: %s", user_id, days, e)
        return None


async def get_latest_pending_manual_invoice(session: AsyncSession, user_id: int) -> Invoice | None:
    """Возвращает последний manual invoice пользователя в статусе WAITING_ADMIN."""
    try:
        invoice_id = await session.scalar(
            select(Invoice.id)
            .where(
                Invoice.user_id == user_id,
                Invoice.provider == "MANUAL",
                Invoice.status == "WAITING_ADMIN",
            )
            .order_by(Invoice.created_at.desc(), Invoice.id.desc())
            .limit(1)
        )
        if invoice_id is None:
            return None
        return await session.get(Invoice, invoice_id)
    except SQLAlchemyError as e:
        logger.error("Ошибка БД в get_latest_pending_manual_invoice user_id=%s: %s", user_id, e)
        return None
    except Exception as e:
        logger.error("Непредвиденная ошибка в get_latest_pending_manual_invoice user_id=%s: %s", user_id, e)
        return None


async def get_billing_entities(session: AsyncSession, ext_id: str) -> tuple[Invoice | None, User | None]:
    """
    Возвращает `(Invoice, User)` через два отдельных запроса с блокировкой строк.
    """
    invoice = await get_invoice_by_external_id(session, ext_id)
    if invoice is None:
        return None, None

    locked_invoice = await session.get(Invoice, invoice.id, with_for_update=True)
    if locked_invoice is None:
        return None, None

    locked_user = await session.get(User, locked_invoice.user_id, with_for_update=True)
    return locked_invoice, locked_user


async def update_invoice_record(
    session: AsyncSession,
    invoice_id: int,
    amount_actual: float,
    status: str,
    *,
    amount_actual_native: float | None = None,
) -> Invoice | None:
    """Обновляет `amount_actual`, (опционально) `amount_actual_native` и `status` у инвойса."""
    invoice = await session.get(Invoice, invoice_id, with_for_update=True)
    if invoice is None:
        return None

    invoice.amount_actual = _round_money(amount_actual)
    invoice.status = status
    if amount_actual_native is not None:
        invoice.amount_actual_native = _round_money(amount_actual_native)
    return invoice


async def update_invoice_review_metadata(
    session: AsyncSession,
    invoice_id: int,
    *,
    approved_by_admin_id: int | None = None,
    screenshot_file_id: str | None = None,
    rejection_reason: str | None = None,
) -> Invoice | None:
    """Обновляет metadata ручной модерации инвойса."""
    invoice = await session.get(Invoice, invoice_id, with_for_update=True)
    if invoice is None:
        return None

    invoice.approved_by_admin_id = approved_by_admin_id
    invoice.screenshot_file_id = screenshot_file_id
    invoice.rejection_reason = rejection_reason
    return invoice


async def reset_invoice_for_retry(session: AsyncSession, invoice_id: int) -> Invoice | None:
    """Возвращает manual invoice в состояние повторной отправки чека."""
    invoice = await session.get(Invoice, invoice_id, with_for_update=True)
    if invoice is None:
        return None

    invoice.status = "PENDING"
    invoice.screenshot_file_id = None
    invoice.approved_by_admin_id = None
    return invoice


async def adjust_user_balance(
    session: AsyncSession,
    user_id: int,
    amount: float,
    tx_type: str,
    description: str | None,
) -> float | None:
    """
    Атомарно меняет баланс пользователя и создает запись в `Transaction`.
    Возвращает новый баланс пользователя.
    """
    user = await session.get(User, user_id, with_for_update=True)
    if user is None:
        return None

    rounded_amount = _round_money(amount)
    user.balance = _round_money(user.balance + rounded_amount)
    session.add(
        Transaction(
            user_id=user_id,
            amount=rounded_amount,
            type=tx_type,
            description=description,
        )
    )
    return _round_money(user.balance)


async def extend_user_subscription(
    session: AsyncSession,
    user_id: int,
    days: int,
) -> datetime | None:
    """Продлевает подписку пользователя и возвращает новую дату окончания."""
    user = await session.get(User, user_id, with_for_update=True)
    if user is None:
        return None

    now = get_utc_now()
    current_end = user.subscription_end if user.subscription_end and user.subscription_end > now else now
    new_end = current_end + timedelta(days=days)
    user.subscription_end = new_end
    return new_end



async def get_all_deposits(session: AsyncSession) -> list[tuple[Transaction, str | None]]:
    """
    Возвращает список всех депозитов с данными пользователей.
    """
    try:
        query = (
            select(Transaction, User.username)
            .outerjoin(User, Transaction.user_id == User.id)
            .where(Transaction.type == 'DEPOSIT')
            .order_by(desc(Transaction.created_at))
        )
        result = await session.execute(query)
        return list(result.all())
    except SQLAlchemyError as e:
        logger.error(f"Ошибка БД в get_all_deposits: {e}")
        return []
    except Exception as e:
        logger.error(f"Непредвиденная ошибка в get_all_deposits: {e}")
        return []

async def get_recent_transactions(
    session: AsyncSession,
    user_id: int,
    limit: int | None = None
) -> list[Transaction]:
    """
    Возвращает последние транзакции пользователя.

    :param session: Асинхронная сессия SQLAlchemy
    :param user_id: ID пользователя
    :param limit: Количество записей (по умолчанию из конфига)
    :return: Список транзакций, отсортированных от новых к старым
    """
    from src.core.config import config
    if limit is None:
        limit = config.TRANSACTION_HISTORY_LIMIT
        
    try:
        query = (
            select(Transaction)
            .where(Transaction.user_id == user_id)
            .order_by(Transaction.created_at.desc())
            .limit(limit)
        )
        result = await session.execute(query)
        return list(result.scalars().all())
    except SQLAlchemyError as e:
        logger.error(f"Ошибка БД в get_recent_transactions для {user_id}: {e}")
        return []
    except Exception as e:
        logger.error(f"Непредвиденная ошибка в get_recent_transactions для {user_id}: {e}")
        return []

async def get_partner_stats(session: AsyncSession, user_id: int) -> tuple[int, float]:
    """
    Возвращает статистику партнерской программы пользователя.

    :param session: Асинхронная сессия SQLAlchemy
    :param user_id: ID пользователя
    :return: (количество приглашенных, сумма бонусов REWARD)
    """
    try:
        invited_count_query = select(func.count(User.id)).where(User.referrer_id == user_id)
        invited_count_result = await session.execute(invited_count_query)
        invited_count = int(invited_count_result.scalar() or 0)

        reward_sum_query = select(func.sum(Transaction.amount)).where(
            Transaction.user_id == user_id,
            Transaction.type == 'REWARD'
        )
        reward_sum_result = await session.execute(reward_sum_query)
        total_rewards = round(float(reward_sum_result.scalar() or 0.0), 2)

        return invited_count, total_rewards
    except SQLAlchemyError as e:
        logger.error(f"Ошибка БД в get_partner_stats для {user_id}: {e}")
        return 0, 0.0
    except Exception as e:
        logger.error(f"Непредвиденная ошибка в get_partner_stats для {user_id}: {e}")
        return 0, 0.0


async def activate_subscription_logic(
    session: AsyncSession, 
    user_id: int, 
    days: int, 
    price: float, 
    description: str
) -> tuple[bool, datetime | None]:
    """
    Унифицированная логика активации подписки.
    Выполняет начисление дней, создание транзакции и расчет реф-бонуса.
    НЕ делает session.commit().
    """
    try:
        user = await session.get(User, user_id, with_for_update=True)
        if not user:
            logger.error(f"Пользователь {user_id} не найден для активации подписки")
            return False, None

        new_end = await extend_user_subscription(session, user_id, days)
        if new_end is None:
            return False, None

        price = round(float(price), 2)

        if user.referrer_id:
            bonus_percent = getattr(config, "REFERRAL_BONUS_PERCENT", 15.0)
            bonus_amount = round(price * (bonus_percent / 100.0), 2)
            if bonus_amount > 0:
                referrer = await session.get(User, user.referrer_id, with_for_update=True)
                if referrer:
                    referrer.balance = round(referrer.balance + bonus_amount, 2)
                    reward_tx = Transaction(
                        user_id=referrer.id,
                        amount=bonus_amount,
                        type='REWARD',
                        description=f"Бонус за активацию подписки рефералом {user_id}"
                    )
                    session.add(reward_tx)
                    logger.info(f"Начислен реф-бонус {bonus_amount} пользователю {referrer.id}")

        return True, new_end
    except Exception as e:
        logger.error(f"Ошибка в activate_subscription_logic для {user_id}: {e}")
        return False, None

async def charge_and_activate_subscription(
    session: AsyncSession,
    user_id: int,
    days: int,
    price: float,
    description: str
) -> tuple[bool, datetime | None, float]:
    """
    Списывает баланс пользователя и активирует подписку в рамках одной транзакции.
    Не делает session.commit().
    """
    try:
        user = await session.get(User, user_id, with_for_update=True)
        if not user:
            logger.warning(f"Попытка активации подписки несуществующим пользователем {user_id}")
            return False, None, 0.0

        price = round(float(price), 2)
        if user.balance < price:
            logger.info(f"Недостаточно средств у {user_id}: {user.balance} < {price}")
            return False, None, 0.0

        new_balance = await adjust_user_balance(
            session=session,
            user_id=user_id,
            amount=-price,
            tx_type="WITHDRAW",
            description=description,
        )
        if new_balance is None:
            return False, None, 0.0

        success, new_end = await activate_subscription_logic(
            session=session,
            user_id=user_id,
            days=days,
            price=price,
            description=description,
        )
        if not success:
            return False, None, 0.0

        bonus_amount = 0.0
        if user.referrer_id:
            bonus_amount = round(price * (config.REFERRAL_BONUS_PERCENT / 100.0), 2)

        return True, new_end, bonus_amount
    except Exception as e:
        logger.error(f"Ошибка в charge_and_activate_subscription для {user_id}: {e}")
        return False, None, 0.0

async def purchase_subscription(session: AsyncSession, user_id: int, days: int, price: float) -> tuple[bool, datetime | None, float]:
    """
    Атомарная покупка подписки:
    1. Проверяет баланс пользователя.
    2. Вызывает логику активации.
    3. Делает commit.
    
    :return: (успех, новая_дата_окончания, сумма_реф_бонуса)
    """
    try:
        success, new_end, bonus_amount = await charge_and_activate_subscription(
            session=session,
            user_id=user_id,
            days=days,
            price=price,
            description=f"Покупка подписки на {days} дн."
        )
        if not success:
            return False, None, 0.0

        await session.commit()
        logger.info(f"Пользователь {user_id} успешно купил подписку на {days} дн. за {price} USDT")
        return True, new_end, bonus_amount
        
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"Ошибка БД при покупке подписки для {user_id}: {e}")
        return False, None, 0.0
    except Exception as e:
        await session.rollback()
        logger.error(f"Непредвиденная ошибка при покупке подписки для {user_id}: {e}")
        return False, None, 0.0
