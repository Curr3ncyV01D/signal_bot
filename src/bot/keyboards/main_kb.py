from math import ceil
from datetime import datetime
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram_i18n import LazyProxy
from aiogram_i18n.types import InlineKeyboardMarkup, InlineKeyboardButton
from src.core.config import config
from src.database.models import User
from src.database.functions import get_utc_now
from src.bot.utils.kb_helper import Kb_Helper
from src.utils import format_smart_num

# ===== Clean State Model Constants (синхронно с commands.py) =====
STATE_TRIAL_AVAILABLE: str = "STATE_TRIAL_AVAILABLE"
STATE_VIP_ACTIVE: str = "STATE_VIP_ACTIVE"
STATE_FREE_ACTIVE: str = "STATE_FREE_ACTIVE"
STATE_FREE_PAUSED: str = "STATE_FREE_PAUSED"

VIP_RENEW_DAYS_THRESHOLD: int = 5


def _get_days_left(subscription_end: datetime | None, now: datetime) -> int | None:
    """Возвращает количество оставшихся полных/частичных суток активной подписки."""
    if subscription_end is None or subscription_end <= now:
        return None

    seconds_left = (subscription_end - now).total_seconds()
    return max(0, ceil(seconds_left / 86400))


def _resolve_state(user: User, is_gate_allowed: bool | None) -> str:
    """
    Resolver пользовательского состояния для UI (копия из commands.py,
    без явного импорта чтобы избежать циклических зависимостей).
    """
    from src.database.crud.user_service import is_user_vip

    if not user.is_trial_used and not is_user_vip(user):
        return STATE_TRIAL_AVAILABLE
    if is_user_vip(user):
        return STATE_VIP_ACTIVE
    if is_gate_allowed is True:
        return STATE_FREE_ACTIVE
    return STATE_FREE_PAUSED


def _build_static_footer(user: User) -> InlineKeyboardBuilder:
    """
    Нижний статичный блок: 3 ряда / 5 кнопок — ИДЕНТИЧЕН во всех 4 состояниях.

    Ряд 1: [ 💰 Кошелек (X.XX USDT) ] | [ 👤 Личный кабинет ]
    Ряд 2: [ ⚙️ Настройки и фильтры ]
    Ряд 3: [ 💬 Чат сообщества ↗ ] | [ 👨‍💻 Тех. поддержка ↗ ]
    """
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text=LazyProxy("kb-main-wallet", balance=format_smart_num(user.balance)),
            callback_data="wallet_main",
        ),
        InlineKeyboardButton(
            text=LazyProxy("kb-main-profile"),
            callback_data="profile_main",
        ),
    )
    builder.row(InlineKeyboardButton(
            text=LazyProxy("kb-main-settings"),
            callback_data="open_settings",
        )
        
    )
    builder.row(
        InlineKeyboardButton(
            text=LazyProxy("kb-main-chat"),
            url=config.COMMUNITY_GROUP_LINK,
        ),
        InlineKeyboardButton(
            text=LazyProxy("kb-main-support"),
            url=config.SUPPORT_URL,
        ),
    )
    return builder


def get_start_kb(
    user: User,
    is_gate_allowed: bool | None = None,
) -> InlineKeyboardMarkup:
    """
    Clean State Model — клавиатура главного меню.

    Структура:
      [ ДИНАМИЧЕСКИЙ СЛОТ (0 или 1 кнопка) ] ← добавляется СВЕРХУ
      [ СТАТИЧЕСКИЙ ФУТЕР: 3 ряда / 5 кнопок ] ← одинаковый ВСЕГДА

    Верхний слот (строго 0 или 1 кнопка):
      • STATE_TRIAL_AVAILABLE → 🎁 Активировать VIP-доступ (3 дня)  (activate_trial)
      • STATE_VIP_ACTIVE:
        - days_left ≤ 5 → ⚡ Продлить VIP-доступ (buy_subscription)
        - days_left > 5 → СЛОТ ПУСТОЙ
      • STATE_FREE_ACTIVE → 💎 Перейти на VIP (Убрать шум) (buy_subscription)
      • STATE_FREE_PAUSED → 🔓 Включить бесплатные сигналы (open_gate_unlock_screen)
    """
    now = get_utc_now()
    state = _resolve_state(user, is_gate_allowed)

    builder = InlineKeyboardBuilder()

    # ===== ДИНАМИЧЕСКИЙ ВЕРХНИЙ СЛОТ (0 или 1 кнопка) =====
    if state == STATE_TRIAL_AVAILABLE:
        builder.row(
            InlineKeyboardButton(
                text=LazyProxy("kb-main-trial"),
                callback_data="activate_trial",
            )
        )
    elif state == STATE_VIP_ACTIVE:
        days_left = _get_days_left(user.subscription_end, now)
        if days_left is not None and days_left <= VIP_RENEW_DAYS_THRESHOLD:
            builder.row(
                InlineKeyboardButton(
                    text=LazyProxy("kb-main-renew-left", days=days_left),
                    callback_data="buy_subscription",
                )
            )
    elif state == STATE_FREE_ACTIVE:
        builder.row(
            InlineKeyboardButton(
                text=LazyProxy("kb-main-upgrade-vip"),
                callback_data="buy_subscription",
            )
        )
    else:  # STATE_FREE_PAUSED
        builder.row(
            InlineKeyboardButton(
                text=LazyProxy("kb-main-unlock-signals"),
                callback_data="open_gate_unlock_screen",
            )
        )

    # ===== СТАТИЧЕСКИЙ ФУТЕР (всегда 3 ряда / 5 кнопок) =====
    static_markup = _build_static_footer(user).as_markup()
    for static_row in static_markup.inline_keyboard:
        builder.row(*static_row)

    return builder.as_markup()


def get_back_button_kb(back_data: str) -> InlineKeyboardMarkup:
    """Клавиатура для возврата в главное меню"""
    return Kb_Helper.add_common_buttons(InlineKeyboardBuilder(), back_data=back_data).as_markup()


def get_close_button_kb() -> InlineKeyboardMarkup:
    """Клавиатура для сообщений уведомлений. Нужно чтобы закрывать их одной кнопкой"""
    return Kb_Helper.add_common_buttons(InlineKeyboardBuilder()).as_markup()
