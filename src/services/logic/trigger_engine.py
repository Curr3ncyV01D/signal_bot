from src.core.dto import SignalAlertType


def is_signal_spammy(
    *,
    last_time: float,
    current_time: float,
    last_sum: float,
    current_sum: float,
    cooldown_limit: float,
    growth_multiplier: float,
) -> bool:
    cooldown_elapsed = (current_time - last_time) >= cooldown_limit
    grew_enough = current_sum >= (last_sum * growth_multiplier)
    return not cooldown_elapsed or not grew_enough


def evaluate_trigger_logic(
    *,
    sum_5m: float,
    sum_1h: float,
    sum_cascade: float,
    cascade_count: int,
    oi_pct: float | None,
    oi_val: float | None,
    volume_threshold: float,
    cascade_threshold: float,
    oi_threshold_pct: float,
    oi_threshold_value: float,
    cascade_trigger_count: int,
    volume_multiplier: float,
    squeeze_ratio: float,
    enable_cascade: bool = True,
    enable_oi: bool = True,
    enable_squeeze: bool = True,
    enable_volume: bool = True,
    require_nonnegative_oi_pct: bool = False,
    current_rsi: float | None = None,
    rsi_min: float = 100.0,
    rsi_max: float = 0.0,
) -> SignalAlertType | None:
    rsi_filter_active = not (rsi_min == 100.0 and rsi_max == 0.0)
    if rsi_filter_active:
        if current_rsi is None:
            return None
        if not (current_rsi <= rsi_min or current_rsi >= rsi_max):
            return None

    has_cascade = (
        cascade_count >= cascade_trigger_count
        and sum_cascade >= cascade_threshold
    )
    has_oi_pump = (
        oi_pct is not None
        and oi_val is not None
        and oi_pct >= oi_threshold_pct
        and abs(oi_val) >= oi_threshold_value
        and (not require_nonnegative_oi_pct or oi_pct >= 0)
    )
    has_volume = (
        sum_5m >= volume_threshold
        or sum_1h >= (volume_threshold * volume_multiplier)
    )
    has_squeeze = has_volume and sum_5m > (sum_1h * squeeze_ratio)

    if has_cascade and enable_cascade:
        return "CASCADE"
    if has_oi_pump and enable_oi:
        return "OI_PUMP"
    if has_squeeze and enable_squeeze:
        return "SQUEEZE"
    if has_volume and enable_volume:
        return "VOLUME"
    return None


def build_alert_title(alert_type: SignalAlertType, cascade_count: int) -> str:
    if alert_type == "CASCADE":
        return f"⚡️ LIQ CASCADE x{cascade_count}"
    if alert_type == "OI_PUMP":
        return "📈 OI PUMP"
    if alert_type == "SQUEEZE":
        return "🔥 QUICK SQUEEZE"
    return "📊 LIQ VOLUME"
