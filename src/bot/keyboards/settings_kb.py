from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram_i18n import LazyProxy
from aiogram_i18n.types import InlineKeyboardButton, InlineKeyboardMarkup
from src.core.config import config
from src.database.models import User
from src.database.crud.user_service import is_user_vip
from src.bot.utils.kb_helper import Kb_Helper


toggle = Kb_Helper.toggle_icon


def _append_vip_unlock_button(builder: InlineKeyboardBuilder, user: User | None) -> None:
    if user is None:
        return
    if is_user_vip(user):
        return
    builder.row(
        InlineKeyboardButton(
            text=LazyProxy("kb-settings-buy-vip"),
            callback_data="buy_subscription",
        )
    )


def get_settings_kb(user: User) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text=LazyProxy("kb-settings-preset-profiles"),
            callback_data="open_setting_presets",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=LazyProxy("kb-settings-open-filters"),
            callback_data="settings_filters",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=LazyProxy("kb-settings-open-display"),
            callback_data="settings_display",
        )
    )
    _append_vip_unlock_button(builder, user)
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-settings-back-main"), callback_data="back_to_main"))
    return builder.as_markup()


def get_settings_filters_kb(user: User) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=LazyProxy("kb-settings-help-liq"),
            callback_data="help_liq",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=LazyProxy("kb-settings-toggle-longs", status=toggle(user.alert_longs)),
            callback_data="toggle_longs",
        ),
        InlineKeyboardButton(
            text=LazyProxy("kb-settings-toggle-shorts", status=toggle(user.alert_shorts)),
            callback_data="toggle_shorts",
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text=LazyProxy("kb-settings-mode", mode=user.threshold_mode),
            callback_data="toggle_threshold_mode",
        )
    )
    if user.threshold_mode == "PERCENT":
        builder.row(
            InlineKeyboardButton(
                text=LazyProxy("kb-settings-threshold-volume-percent"),
                callback_data="set_mcap_pct",
            ),
            InlineKeyboardButton(
                text=LazyProxy("kb-settings-threshold-cascade-percent"),
                callback_data="set_mcap_cas_pct",
            ),
        )
        builder.row(
            InlineKeyboardButton(
                text=LazyProxy("kb-settings-threshold-min-usd"),
                callback_data="set_mcap_min_usd",
            ),
            InlineKeyboardButton(
                text=LazyProxy("kb-settings-threshold-cascade-min-usd"),
                callback_data="set_mcap_cas_min_usd",
            ),
        )
    else:
        builder.row(
            InlineKeyboardButton(
                text=LazyProxy("kb-settings-threshold-volume-usd"),
                callback_data="set_threshold",
            ),
            InlineKeyboardButton(
                text=LazyProxy("kb-settings-threshold-cascade-usd"),
                callback_data="set_cascade_threshold",
            ),
        )

    builder.row(
        InlineKeyboardButton(
            text=LazyProxy("kb-settings-toggle-cascade", status=toggle(user.alert_cascade)),
            callback_data="toggle_cascade",
        ),
        InlineKeyboardButton(
            text=LazyProxy("kb-settings-toggle-volume", status=toggle(user.alert_volume)),
            callback_data="toggle_volume",
        ),
        InlineKeyboardButton(
            text=LazyProxy("kb-settings-toggle-squeeze", status=toggle(user.alert_squeeze)),
            callback_data="toggle_squeeze",
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text=LazyProxy("kb-settings-oi-thresholds"),
            callback_data="menu_oi_thresholds",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=LazyProxy(
                "kb-settings-rsi-thresholds",
                rsi_min=str(_format_rsi(user.filter_rsi_min)),
                rsi_max=str(_format_rsi(user.filter_rsi_max)),
            ),
            callback_data="menu_rsi_thresholds",
        )
    )
    _append_vip_unlock_button(builder, user)
    builder.row(
        InlineKeyboardButton(
            text=LazyProxy("kb-settings-back-root"),
            callback_data="back_to_settings",
        )
    )
    return builder.as_markup()


def get_settings_display_kb(user: User) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=LazyProxy("kb-settings-help-analytics"),
            callback_data="help_analytics",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=LazyProxy("kb-settings-toggle-rsi", status=toggle(user.alert_rsi)),
            callback_data="toggle_rsi",
        ),
        InlineKeyboardButton(
            text=LazyProxy("kb-settings-toggle-oi", status=toggle(user.alert_oi)),
            callback_data="toggle_oi",
        ),
        InlineKeyboardButton(
            text=LazyProxy("kb-settings-toggle-cvd", status=toggle(user.alert_cvd)),
            callback_data="toggle_cvd",
        )
    )
    _append_vip_unlock_button(builder, user)
    builder.row(
        InlineKeyboardButton(
            text=LazyProxy("kb-settings-back-root"),
            callback_data="back_to_settings",
        )
    )
    return builder.as_markup()


def get_back_to_settings_kb(back_callback_data: str = "back_to_settings") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=LazyProxy("kb-settings-ask-question"), url=config.SUPPORT_URL))
    builder.row(
        InlineKeyboardButton(
            text=LazyProxy("kb-settings-back"),
            callback_data=back_callback_data,
        )
    )
    return builder.as_markup()


def get_presets_selection_kb(user: User | None = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=LazyProxy("kb-settings-preset-scalper"),
            callback_data="open_setting_preset_SCALPER",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=LazyProxy("kb-settings-preset-balanced"),
            callback_data="open_setting_preset_BALANCED",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=LazyProxy("kb-settings-preset-conservative"),
            callback_data="open_setting_preset_CONSERVATIVE",
        )
    )
    _append_vip_unlock_button(builder, user)
    builder.row(
        InlineKeyboardButton(
            text=LazyProxy("kb-settings-back"),
            callback_data="back_to_settings",
        )
    )
    return builder.as_markup()


def get_preset_confirmation_kb(preset_id: str, user: User | None = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=LazyProxy("kb-settings-preset-confirm-apply"),
            callback_data=f"apply_setting_preset_{preset_id}",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=LazyProxy("kb-settings-preset-confirm-cancel"),
            callback_data="open_setting_presets",
        )
    )
    _append_vip_unlock_button(builder, user)
    return builder.as_markup()


def _format_rsi(value: float) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return 0


def get_settings_rsi_kb(user: User | None = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text=LazyProxy("kb-settings-rsi-preset-conservative"),
            callback_data="set_rsi_preset_CONSERVATIVE",
        ),
        InlineKeyboardButton(
            text=LazyProxy("kb-settings-rsi-preset-balanced"),
            callback_data="set_rsi_preset_BALANCED",
        ),
        InlineKeyboardButton(
            text=LazyProxy("kb-settings-rsi-preset-scalper"),
            callback_data="set_rsi_preset_SCALPER",
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text=LazyProxy("kb-settings-rsi-disable"),
            callback_data="set_rsi_preset_DISABLED",
        ),
        InlineKeyboardButton(
            text=LazyProxy("kb-settings-rsi-manual"),
            callback_data="set_rsi_manual_start",
        )
    )
    _append_vip_unlock_button(builder, user)
    builder.row(
        InlineKeyboardButton(
            text=LazyProxy("kb-settings-rsi-back"),
            callback_data="settings_filters",
        )
    )
    return builder.as_markup()
