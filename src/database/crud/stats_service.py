import time
from datetime import datetime, timedelta
from sqlalchemy import select, func, and_, desc, case
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.models import User, Transaction
from src.database.functions import get_utc_now

# Простой кеш в памяти
_stats_cache = {}
_last_update = {}
CACHE_TTL = 300  # 5 минут

async def _get_cached_data(cache_key: str, force_refresh: bool, fetch_func, *args, **kwargs):
    """Вспомогательная функция для кеширования."""
    now_ts = time.time()
    if not force_refresh and cache_key in _stats_cache:
        if now_ts - _last_update.get(cache_key, 0) < CACHE_TTL:
            return _stats_cache[cache_key]
    
    data = await fetch_func(*args, **kwargs)
    _stats_cache[cache_key] = data
    _last_update[cache_key] = now_ts
    return data

async def get_financial_metrics(session: AsyncSession, force_refresh: bool = False) -> dict:
    """
    Возвращает финансовые метрики (USDT):
    - Оборот за 24ч, 7д, Total
    - Дельта оборота (24ч к предыдущим 24ч)
    - Выплачено бонусов (REWARD)
    - Бонусный долг (SUM balance)
    - ARPU
    """
    return await _get_cached_data("financial", force_refresh, _fetch_financial_metrics, session)

async def _fetch_financial_metrics(session: AsyncSession) -> dict:
    """Прямой расчет финансовых метрик одним SQL-запросом."""
    now = get_utc_now()
    day_ago = now - timedelta(days=1)
    two_days_ago = now - timedelta(days=2)
    seven_days_ago = now - timedelta(days=7)

    # Считаем все обороты за один проход по таблице Transactions
    turnover_query = select(
        func.sum(case((Transaction.created_at >= day_ago, Transaction.amount), else_=0)).label("t24h"),
        func.sum(case((and_(Transaction.created_at >= two_days_ago, Transaction.created_at < day_ago), Transaction.amount), else_=0)).label("t_prev24h"),
        func.sum(case((Transaction.created_at >= two_days_ago, Transaction.amount), else_=0)).label("t48h"),
        func.sum(case((Transaction.created_at >= seven_days_ago, Transaction.amount), else_=0)).label("t7d"),
        func.sum(Transaction.amount).label("total"),
        func.count(func.distinct(Transaction.user_id)).label("unique_payers")
    ).where(Transaction.type == 'DEPOSIT')

    res = (await session.execute(turnover_query)).one()
    
    t24h = res.t24h or 0.0               # Оборот за 24 часа
    t_prev24h = res.t_prev24h or 0.0     # Оборот за предыдущи 24 часа
    t48h = res.t48h or 0.0               # Оборот за 48 часов
    t7d = res.t7d or 0.0                 # Оборот за 7 дней
    total = res.total or 0.0             # Оборот за всё время
    unique_payers = res.unique_payers or 0

    # Дельта (%)
    delta = 0.0
    if t_prev24h > 0:
        delta = ((t24h - t_prev24h) / t_prev24h) * 100
    elif t24h > 0:
        delta = 100.0

    # Выплачено бонусов
    rewards_query = select(func.sum(Transaction.amount)).where(Transaction.type == 'REWARD')
    rewards_total = (await session.execute(rewards_query)).scalar() or 0.0

    # Бонусный долг (Количество денег на всех кошелках)
    bonus_debt_query = select(func.sum(User.balance))
    bonus_debt = (await session.execute(bonus_debt_query)).scalar() or 0.0

    # ARPU - доход с одного пользователя за всё время
    arpu = total / unique_payers if unique_payers > 0 else 0.0

    return {
        "turnover_24h": round(t24h, 2),
        "turnover_48h": round(t48h, 2),
        "turnover_7d": round(t7d, 2),
        "turnover_total": round(total, 2),
        "delta_24h": round(delta, 1),
        "rewards_total": round(abs(rewards_total), 2),
        "bonus_debt": round(bonus_debt, 2),
        "arpu": round(arpu, 2)
    }

async def get_audience_metrics(session: AsyncSession, force_refresh: bool = False) -> dict:
    """
    Возвращает метрики аудитории:
    - Всего пользователей
    - Активные VIP-подписки
    - Конверсия Trial-to-Paid
    - Топ-3 реферера
    """
    return await _get_cached_data("audience", force_refresh, _fetch_audience_metrics, session)

async def _fetch_audience_metrics(session: AsyncSession) -> dict:
    """Прямой расчет метрик аудитории."""
    now = get_utc_now()

    # 1. Основные счетчики
    counts_query = select(
        func.count(User.id).label("total"),
        func.sum(case((User.subscription_end > now, 1), else_=0)).label("active_vip"),
        func.sum(case((User.is_trial_used == True, 1), else_=0)).label("trial_used")
    )
    res_counts = (await session.execute(counts_query)).one()
    
    # 2. Конверсия
    trial_user_ids_subquery = select(User.id).where(User.is_trial_used == True).scalar_subquery()

    paid_from_trial_query = select(func.count(func.distinct(Transaction.user_id))).where(
        and_(Transaction.type == 'WITHDRAW',
         Transaction.user_id.in_(trial_user_ids_subquery))
    )
    paid_from_trial_count = (await session.execute(paid_from_trial_query)).scalar() or 0
    conversion = (paid_from_trial_count / res_counts.trial_used * 100) if res_counts.trial_used and res_counts.trial_used > 0 else 0.0

    # 3. Топ-3 Реферера
    counts_subquery = (
        select(User.referrer_id, func.count(User.id).label('invite_count'))
        .where(User.referrer_id.isnot(None))
        .group_by(User.referrer_id)
        .subquery()
    )

    top_referrers_query = (
        select(User.id, User.username, counts_subquery.c.invite_count)
        .join(counts_subquery, User.id == counts_subquery.c.referrer_id)
        .order_by(desc(counts_subquery.c.invite_count))
        .limit(3)
    )
    top_referrers_res = (await session.execute(top_referrers_query)).all()
    top_reffers = [{"name": r.username or f"ID: {r.id}", "count": r.invite_count} for r in top_referrers_res]

    return {
        "total_users": res_counts.total or 0,
        "active_vip": res_counts.active_vip or 0,
        "trial_users_count": res_counts.trial_used or 0,
        "paid_from_trial_count": paid_from_trial_count,
        "conversion_rate": round(conversion, 1),
        "top_referrers": top_reffers
    }
