from typing import Literal, TypedDict


type SignalSideLabel = Literal["LONG", "SHORT"]
type SignalAlertType = Literal["CASCADE", "OI_PUMP", "SQUEEZE", "VOLUME"]
type SignalOhlcRow = list[int | float]


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
    market_data: SignalMarketData
    impact_metrics: SignalImpactMetrics
    trade_metrics: SignalTradeMetrics
    settings: SignalSettings
    ohlc_history: list[SignalOhlcRow]
    chart_file_id: str | None
    timestamp: float
