import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, desc
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload
from datetime import datetime
from src.database.models import User, Transaction, Invoice

logger = logging.getLogger(__name__)

async def add_balance(
    session: AsyncSession, 
    user_id: int, 
    amount: float, 
    tx_type: str, 
    description: str | None = None
) -> bool:
    """
    Атомарно увеличивает баланс пользователя и создает запись в истории транзакций.
    
    :param session: Асинхронная сессия SQLAlchemy
    :param user_id: ID пользователя (Telegram ID)
    :param amount: Сумма пополнения
    :param tx_type: Тип транзакции ('DEPOSIT', 'REWARD', и т.д.)
    :param description: Описание операции
    :return: True если успешно, иначе False
    """
    try:
        amount = round(float(amount), 2)
        user = await session.get(User, user_id, with_for_update=True)
        if not user:
            logger.warning(f"Попытка пополнить баланс несуществующему пользователю {user_id}")
            return False
        
        user.balance = round(user.balance + amount, 2)
        
        tx = Transaction(
            user_id=user_id,
            amount=amount,
            type=tx_type,
            description=description
        )
        session.add(tx)
        await session.commit()
        logger.info(f"Баланс пользователя {user_id} пополнен на {amount} ({tx_type})")
        return True
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"Ошибка БД в add_balance для {user_id}: {e}")
        return False
    except Exception as e:
        await session.rollback()
        logger.error(f"Непредвиденная ошибка в add_balance для {user_id}: {e}")
        return False

async def spend_balance(
    session: AsyncSession, 
    user_id: int, 
    amount: float, 
    description: str | None = None
) -> bool:
    """
    Атомарно списывает средства с баланса пользователя, если их достаточно.
    
    :param session: Асинхронная сессия SQLAlchemy
    :param user_id: ID пользователя (Telegram ID)
    :param amount: Сумма списания
    :param description: Описание операции
    :return: True если списание успешно, False если недостаточно средств или ошибка
    """
    try:
        amount = round(float(amount), 2)
        user = await session.get(User, user_id, with_for_update=True)
        
        if not user:
            logger.warning(f"Попытка списания у несуществующего пользователя {user_id}")
            return False
            
        if user.balance < amount:
            logger.info(f"Недостаточно средств у пользователя {user_id}: balance={user.balance}, required={amount}")
            return False
            
        user.balance = round(user.balance - amount, 2)
        
        tx = Transaction(
            user_id=user_id,
            amount=-amount,
            type='WITHDRAW',
            description=description
        )
        session.add(tx)
        await session.commit()
        logger.info(f"С баланса пользователя {user_id} списано {amount} (WITHDRAW)")
        return True
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"Ошибка БД в spend_balance для {user_id}: {e}")
        return False
    except Exception as e:
        await session.rollback()
        logger.error(f"Непредвиденная ошибка в spend_balance для {user_id}: {e}")
        return False

async def create_invoice(
    session: AsyncSession,
    user_id: int,
    amount: float,
    crypto_pay_id: str
) -> Invoice | None:
    """
    Создает новый инвойс для оплаты.
    
    :param session: Асинхронная сессия SQLAlchemy
    :param user_id: ID пользователя
    :param amount: Сумма инвойса
    :param crypto_pay_id: Внешний ID из CryptoPay
    :return: Объект Invoice или None при ошибке
    """
    try:
        invoice = Invoice(
            user_id=user_id,
            amount=round(float(amount), 2),
            crypto_pay_id=crypto_pay_id,
            status='PENDING'
        )
        session.add(invoice)
        await session.commit()
        logger.info(f"Создан инвойс {crypto_pay_id} для пользователя {user_id} на сумму {amount}")
        return invoice
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"Ошибка БД в create_invoice для {user_id}: {e}")
        return None
    except Exception as e:
        await session.rollback()
        logger.error(f"Непредвиденная ошибка в create_invoice для {user_id}: {e}")
        return None

async def get_invoice_by_ext_id(session: AsyncSession, ext_id: str) -> Invoice | None:
    """
    Получает инвойс по его внешнему идентификатору.
    
    :param session: Асинхронная сессия SQLAlchemy
    :param ext_id: Внешний ID (crypto_pay_id)
    :return: Объект Invoice или None
    """
    try:
        query = select(Invoice).where(Invoice.crypto_pay_id == ext_id)
        result = await session.execute(query)
        return result.scalar_one_or_none()
    except SQLAlchemyError as e:
        logger.error(f"Ошибка БД в get_invoice_by_ext_id {ext_id}: {e}")
        return None
    except Exception as e:
        logger.error(f"Непредвиденная ошибка в get_invoice_by_ext_id {ext_id}: {e}")
        return None

async def update_invoice_status(session: AsyncSession, ext_id: str, status: str) -> bool:
    """
    Обновляет статус инвойса.
    
    :param session: Асинхронная сессия SQLAlchemy
    :param ext_id: Внешний ID (crypto_pay_id)
    :param status: Новый статус ('PAID', 'EXPIRED', и т.д.)
    :return: True если успешно, иначе False
    """
    try:
        query = update(Invoice).where(Invoice.crypto_pay_id == ext_id).values(status=status)
        result = await session.execute(query)
        if result.rowcount == 0:
            logger.warning(f"Инвойс {ext_id} не найден для обновления статуса")
            return False
            
        await session.commit()
        logger.info(f"Статус инвойса {ext_id} изменен на {status}")
        return True
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"Ошибка БД в update_invoice_status {ext_id}: {e}")
        return False
    except Exception as e:
        await session.rollback()
        logger.error(f"Непредвиденная ошибка в update_invoice_status {ext_id}: {e}")
        return False



async def get_all_deposits(session: AsyncSession) -> list[Transaction]:
    """
    Возвращает список всех депозитов с данными пользователей.
    """
    try:
        query = (
            select(Transaction)
            .options(joinedload(Transaction.user))
            .where(Transaction.type == 'DEPOSIT')
            .order_by(desc(Transaction.created_at))
        )
        result = await session.execute(query)
        return list(result.scalars().all())
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

async def confirm_invoice_payment(session: AsyncSession, ext_id: str) -> bool:
    """
    Атомарно подтверждает оплату инвойса: 
    1. Начисляет баланс пользователю.
    2. Создает транзакцию DEPOSIT.
    3. Меняет статус инвойса на 'PAID'.
    
    Все операции выполняются в рамках одной транзакции БД.
    
    :param session: Асинхронная сессия SQLAlchemy
    :param ext_id: Внешний ID инвойса (crypto_pay_id)
    :return: True если успешно, иначе False
    """
    try:
        # 1. Получаем инвойс и блокируем его
        query = select(Invoice).where(Invoice.crypto_pay_id == ext_id).with_for_update()
        result = await session.execute(query)
        invoice = result.scalar_one_or_none()
        
        if not invoice:
            logger.warning(f"Инвойс {ext_id} не найден для подтверждения оплаты")
            return False
            
        if invoice.status != 'PENDING':
            logger.warning(f"Попытка повторного подтверждения инвойса {ext_id} (текущий статус: {invoice.status})")
            return False

        # 2. Получаем пользователя и блокируем строку
        user = await session.get(User, invoice.user_id, with_for_update=True)
        if not user:
            logger.error(f"Пользователь {invoice.user_id} не найден для начисления по инвойсу {ext_id}")
            return False

        # 3. Начисляем баланс
        amount = round(float(invoice.amount), 2)
        user.balance = round(user.balance + amount, 2)

        # 4. Создаем запись транзакции
        tx = Transaction(
            user_id=invoice.user_id,
            amount=amount,
            type='DEPOSIT',
            description=f"Пополнение через CryptoPay (Invoice #{ext_id})"
        )
        session.add(tx)

        # 5. Обновляем статус инвойса
        invoice.status = 'PAID'
        
        # 6. Фиксируем всё разом
        await session.commit()
        logger.info(f"Оплата инвойса {ext_id} успешно подтверждена. Пользователю {invoice.user_id} начислено {amount} USDT.")
        return True
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"Ошибка БД при подтверждении оплаты инвойса {ext_id}: {e}")
        return False
    except Exception as e:
        await session.rollback()
        logger.error(f"Непредвиденная ошибка при подтверждении оплаты инвойса {ext_id}: {e}")
        return False

async def purchase_subscription(session: AsyncSession, user_id: int, days: int, price: float) -> tuple[bool, datetime | None, float]:
    """
    Атомарная покупка подписки:
    1. Проверяет баланс пользователя.
    2. Списывает средства (WITHDRAW).
    3. Создает запись транзакции.
    4. Продлевает подписка (subscription_end).
    
    Все операции в одной транзакции с блокировкой строки пользователя.
    
    :return: (успех, новая_дата_окончания, сумма_реф_бонуса)
    """
    from src.database.functions import get_utc_now
    from datetime import timedelta
    
    bonus_amount = 0.0
    try:
        # 1. Получаем пользователя и блокируем строку
        user = await session.get(User, user_id, with_for_update=True)
        if not user:
            logger.warning(f"Попытка покупки подписки несуществующим пользователем {user_id}")
            return False, None, 0.0
            
        price = round(float(price), 2)
        if user.balance < price:
            logger.info(f"Недостаточно средств у {user_id}: {user.balance} < {price}")
            return False, None, 0.0
            
        # 2. Списываем баланс
        user.balance = round(user.balance - price, 2)
        
        # 3. Продлеваем подписку
        now = get_utc_now()
        current_end = user.subscription_end if user.subscription_end and user.subscription_end > now else now
        new_end = current_end + timedelta(days=days)
        user.subscription_end = new_end
        
        # 4. Создаем транзакцию
        tx = Transaction(
            user_id=user_id,
            amount=-price,
            type='WITHDRAW',
            description=f"Покупка подписки на {days} дн."
        )
        session.add(tx)
        # 5. Реферальный бонус
        if user.referrer_id:
            from src.core.config import config
            bonus_amount = round(price * (config.REFERRAL_BONUS_PERCENT / 100.0), 2)
            if bonus_amount > 0:
                referrer = await session.get(User, user.referrer_id, with_for_update=True)
                if referrer:
                    referrer.balance = round(referrer.balance + bonus_amount, 2)
                    bonus_tx = Transaction(
                        user_id=referrer.id,
                        amount=bonus_amount,
                        type='REWARD',
                        description=f"Бонус за покупку реферала {user_id}"
                    )
                    session.add(bonus_tx)
                    logger.info(f"Начислен бонус {bonus_amount} USDT пользователю {referrer.id} за покупку {user_id}")
        
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
