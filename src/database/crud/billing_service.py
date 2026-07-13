import logging
from datetime import datetime, timedelta
from sqlalchemy import desc, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import config
from src.database.functions import get_utc_now
from src.database.models import Invoice, Transaction, User

logger = logging.getLogger(__name__)

DEFAULT_PAYMENT_PROVIDER = "CRYPTOMUS"


def _round_money(value: float | int | None) -> float:
    if value is None:
        return 0.0
    return round(float(value), 2)

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
) -> Invoice | None:
    """
    Создает новый инвойс для оплаты.
    
    :param session: Асинхронная сессия SQLAlchemy
    :param user_id: ID пользователя
    :param external_id: Внешний ID провайдера
    :param amount_expected: Ожидаемая сумма инвойса
    :param payload: Дополнительная информация (например, 'sub_30')
    :return: Объект Invoice или None при ошибке
    """
    try:
        rounded_amount_expected = round(float(amount_expected), 2)
        rounded_amount_actual = round(float(amount_actual), 2)
        invoice = Invoice(
            user_id=user_id,
            external_id=str(external_id),
            provider=provider,
            address=address,
            network=network,
            amount_expected=rounded_amount_expected,
            amount_actual=rounded_amount_actual,
            status='PENDING',
            payload=payload
        )
        session.add(invoice)
        await session.commit()
        logger.info(
            "Создан инвойс %s provider=%s для пользователя %s на сумму %s (payload=%s)",
            external_id,
            provider,
            user_id,
            rounded_amount_expected,
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
) -> Invoice | None:
    """Обновляет `amount_actual` и `status` у инвойса."""
    invoice = await session.get(Invoice, invoice_id, with_for_update=True)
    if invoice is None:
        return None

    invoice.amount_actual = _round_money(amount_actual)
    invoice.status = status
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
