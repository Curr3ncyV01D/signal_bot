from dataclasses import dataclass
from datetime import datetime
from typing import Literal, TypedDict


type SignalSideLabel = Literal["LONG", "SHORT"]
type SignalAlertType = Literal["CASCADE", "OI_PUMP", "SQUEEZE", "VOLUME"]
type SignalOhlcRow = list[int | float]
type SettingPresetId = Literal["SCALPER", "BALANCED", "CONSERVATIVE"]
type UserOnboardingStep = Literal["LANGUAGE", "COMMUNITY_BONUS", "PRESET_SELECTION", "COMPLETED"]


class SignalMarketData(TypedDict):
    sum_5m: float
    sum_1h: float
    sum_cascade: float
    cascade_count: int
    oi_pct: float | None
    oi_val: float
    price_pct: float | None
    total_oi: float
    funding: float
    rsi: float | None


class SignalImpactMetrics(TypedDict):
    cap_ratio: float | None
    vol_ratio: float | None
    live_mcap: float
    is_fallback: bool


class SignalTradeMetrics(TypedDict):
    delta_5m: float | None
    delta_30m: float | None


class SignalSettings(TypedDict):
    show_oi: bool
    show_cvd: bool
    show_rsi: bool
    used_mcap: bool


class SignalDTO(TypedDict):
    signal_id: str
    symbol: str
    side_label: SignalSideLabel
    alert_type: SignalAlertType
    alert_title: str
    render_requested: bool
    market_data: SignalMarketData
    impact_metrics: SignalImpactMetrics
    trade_metrics: SignalTradeMetrics
    settings: SignalSettings
    ohlc_history: list[SignalOhlcRow]
    chart_message_id: int | None
    timestamp: float


@dataclass(slots=True, frozen=True)
class SettingPresetDTO:
    threshold: float
    threshold_cascade: float
    threshold_mode: Literal["USD", "PERCENT"]
    threshold_oi_percent: float
    threshold_oi_value: float
    threshold_mcap_pct: float
    threshold_mcap_usd_min: float
    threshold_cascade_mcap_pct: float
    threshold_cascade_mcap_usd_min: float
    rsi_min: float
    rsi_max: float
    alert_cascade: bool
    alert_volume: bool
    alert_squeeze: bool
    alert_longs: bool
    alert_shorts: bool
    alert_oi: bool
    alert_rsi: bool
    alert_cvd: bool


@dataclass(slots=True)
class PaymentUpdateDTO:
    is_paid: bool
    delta_credited: float
    sub_activated: bool
    new_balance: float
    new_end_date: datetime | None
    error: str | None
    admin_name: str | None = None
    amount_actual: float = 0.0
    amount_expected: float = 0.0
    invoice_status: str = "PENDING"
    needed_amount: float = 0.0
    intent_action: str | None = None
    intent_days: int | None = None
