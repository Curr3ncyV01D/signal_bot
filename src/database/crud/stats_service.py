import time
from datetime import datetime, timedelta
from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.models import User, Transaction
from src.database.functions import get_utc_now

# Простой кеш в памяти
_stats_cache = {}
_last_update = {}
CACHE_TTL = 300  # 5 минут

async def get_financial_metrics(session: AsyncSession, force_refresh: bool = False) -> dict:
    """
    Возвращает финансовые метрики (USDT):
    - Оборот за 24ч, 7д, Total
    - Дельта оборота (24ч к предыдущим 24ч)
    - Выплачено бонусов (REWARD)
    - Бонусный долг (SUM balance)
    - ARPU
    """
    now_ts = time.time()
    # Проверяем кеш
    if not force_refresh and "financial" in _stats_cache:
        if now_ts - _last_update.get("financial", 0) < CACHE_TTL:
            return _stats_cache["financial"]

    now = get_utc_now()
    day_ago = now - timedelta(days=1)
    two_days_ago = now - timedelta(days=2)
    seven_days_ago = now - timedelta(days=7)

    # 1. Оборот за 24ч (DEPOSIT)
    turnover_24h_query = select(func.sum(Transaction.amount)).where(
        and_(Transaction.type == 'DEPOSIT', Transaction.created_at >= day_ago)
    )
    turnover_24h = (await session.execute(turnover_24h_query)).scalar() or 0.0

    # 1.1 Оборот за 48ч (DEPOSIT)
    turnover_48h_query = select(func.sum(Transaction.amount)).where(
        and_(Transaction.type == 'DEPOSIT', Transaction.created_at >= two_days_ago)
    )
    turnover_48h = (await session.execute(turnover_48h_query)).scalar() or 0.0

    # 2. Оборот за предыдущие 24ч (для дельты)
    turnover_prev_24h_query = select(func.sum(Transaction.amount)).where(
        and_(
            Transaction.type == 'DEPOSIT',
            Transaction.created_at >= two_days_ago,
            Transaction.created_at < day_ago
        )
    )
    turnover_prev_24h = (await session.execute(turnover_prev_24h_query)).scalar() or 0.0

    # Расчет дельты (%)
    delta = 0.0
    if turnover_prev_24h > 0:
        delta = ((turnover_24h - turnover_prev_24h) / turnover_prev_24h) * 100
    elif turnover_24h > 0:
        delta = 100.0

    # 3. Оборот за 7 дней
    turnover_7d_query = select(func.sum(Transaction.amount)).where(
        and_(Transaction.type == 'DEPOSIT', Transaction.created_at >= seven_days_ago)
    )
    turnover_7d = (await session.execute(turnover_7d_query)).scalar() or 0.0

    # 4. Общий оборот (Total Deposit)
    turnover_total_query = select(func.sum(Transaction.amount)).where(Transaction.type == 'DEPOSIT')
    turnover_total = (await session.execute(turnover_total_query)).scalar() or 0.0

    # 5. Выплачено бонусов (total REWARD)
    rewards_total_query = select(func.sum(Transaction.amount)).where(Transaction.type == 'REWARD')
    rewards_total = (await session.execute(rewards_total_query)).scalar() or 0.0

    # 6. Бонусный долг (Wallet Liabilities - сумма всех балансов)
    bonus_debt_query = select(func.sum(User.balance))
    bonus_debt = (await session.execute(bonus_debt_query)).scalar() or 0.0

    # 7. ARPU (Total Turnover / Unique Payers)
    unique_payers_query = select(func.count(func.distinct(Transaction.user_id))).where(Transaction.type == 'DEPOSIT')
    unique_payers = (await session.execute(unique_payers_query)).scalar() or 0
    
    arpu = turnover_total / unique_payers if unique_payers > 0 else 0.0

    metrics = {
        "turnover_24h": round(turnover_24h, 2),
        "turnover_48h": round(turnover_48h, 2),
        "turnover_7d": round(turnover_7d, 2),
        "turnover_total": round(turnover_total, 2),
        "delta_24h": round(delta, 1),
        "rewards_total": round(abs(rewards_total), 2),
        "bonus_debt": round(bonus_debt, 2),
        "arpu": round(arpu, 2)
    }

    _stats_cache["financial"] = metrics
    _last_update["financial"] = now_ts
    return metrics

async def get_audience_metrics(session: AsyncSession, force_refresh: bool = False) -> dict:
    """
    Возвращает метрики аудитории:
    - Всего пользователей
    - Активные VIP-подписки
    - Конверсия Trial-to-Paid
    - Топ-3 реферера
    """
    now_ts = time.time()
    # Проверяем кеш
    if not force_refresh and "audience" in _stats_cache:
        if now_ts - _last_update.get("audience", 0) < CACHE_TTL:
            return _stats_cache["audience"]

    now = get_utc_now()

    # 1. Всего пользователей
    total_users_query = select(func.count(User.id))
    total_users = (await session.execute(total_users_query)).scalar() or 0

    # 2. Активные VIP-подписки (subscription_end > now)
    active_vip_query = select(func.count(User.id)).where(User.subscription_end > now)
    active_vip = (await session.execute(active_vip_query)).scalar() or 0

    # 3. Конверсия Trial-to-Paid (%)
    # Знаменатель: Юзеры, использовавшие триал
    trial_users_query = select(func.count(User.id)).where(User.is_trial_used == True)
    trial_users_count = (await session.execute(trial_users_query)).scalar() or 0

    # Числитель: Юзеры с триалом, совершившие покупку (WITHDRAW)
    # Используем подзапрос для фильтрации
    trial_user_ids_subquery = select(User.id).where(User.is_trial_used == True).scalar_subquery()
    
    paid_from_trial_query = select(func.count(func.distinct(Transaction.user_id))).where(
        and_(
            Transaction.type == 'WITHDRAW',
            Transaction.user_id.in_(trial_user_ids_subquery)
        )
    )
    paid_from_trial_count = (await session.execute(paid_from_trial_query)).scalar() or 0

    conversion = (paid_from_trial_count / trial_users_count * 100) if trial_users_count > 0 else 0.0

    # 4. Топ-3 Реферера
    # Группируем по referrer_id и считаем приглашенных
    counts_subquery = (
        select(User.referrer_id, func.count(User.id).label('invite_count'))
        .where(User.referrer_id.isnot(None))
        .group_by(User.referrer_id)
        .subquery()
    )

    # Джойним с User для получения имен
    top_referrers_query = (
        select(User.id, User.username, counts_subquery.c.invite_count)
        .join(counts_subquery, User.id == counts_subquery.c.referrer_id)
        .order_by(desc(counts_subquery.c.invite_count))
        .limit(3)
    )
    top_referrers_res = (await session.execute(top_referrers_query)).all()

    top_referrers = []
    for ref_id, username, count in top_referrers_res:
        name = username if username else f"ID: {ref_id}"
        top_referrers.append({"name": name, "count": count})

    metrics = {
        "total_users": total_users,
        "active_vip": active_vip,
        "trial_users_count": trial_users_count,
        "paid_from_trial_count": paid_from_trial_count,
        "conversion_rate": round(conversion, 1),
        "top_referrers": top_referrers
    }

    _stats_cache["audience"] = metrics
    _last_update["audience"] = now_ts
    return metrics
