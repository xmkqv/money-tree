from datetime import datetime
from typing import Annotated, Self

from pydantic import AfterValidator, AnyHttpUrl, Field, model_validator

from .values import (
    CHART_TIMEFRAMES,
    Amount,
    BrokerMode,
    ChartTimeframe,
    Count,
    DataFeedName,
    EquityPeriod,
    EquityTimeframe,
    Fraction,
    MaxAge,
    OptionalFraction,
    RequiredSecret,
    SettingsSection,
    SigningSecret,
    Timeframe,
)


class TimeoutSection(SettingsSection):
    connect_seconds: Amount
    read_seconds: Amount
    write_seconds: Amount
    pool_seconds: Amount


class BrokerSection(SettingsSection):
    mode: BrokerMode
    api_key: RequiredSecret
    api_secret: RequiredSecret
    timeout: TimeoutSection


class FinnhubSection(SettingsSection):
    api_key: RequiredSecret
    timeout: TimeoutSection


class BarsSection(SettingsSection):
    intraday_feed: DataFeedName
    daily_feed: DataFeedName
    timeout: TimeoutSection


class RiskSection(SettingsSection):
    per_day_max: Fraction
    per_trade_max: Fraction
    position_fraction_max: Fraction
    positions_max: Count
    notional_usd_min: Amount
    quantity_decimal_places: Count

    @model_validator(mode="after")
    def check_limits(self) -> Self:
        if self.per_trade_max > self.per_day_max:
            raise ValueError("risk per trade must not exceed risk per day")
        return self


class ExportSection(SettingsSection):
    url: AnyHttpUrl
    secret: SigningSecret
    interval_seconds: Count
    events_max: Count
    timeout_seconds: Amount
    close_timeout_seconds: Amount


class ScreenSection(SettingsSection):
    price_usd_min: Amount
    turnover_usd_min: Amount
    turnover_sessions: Count
    lookback_days: Count


class PortfolioSection(SettingsSection):
    symbols_per_request: Count
    orders_per_request: Count
    lookback_days: Count
    pending_ttl_minutes: Count
    opening_lead_minutes: Count
    iteration_minutes: Count
    stop_coverage_drift_max: Amount


class EarningsSection(SettingsSection):
    block_days: Count
    calendar_cache_max: Count


class BacktestSection(SettingsSection):
    asset_defaults: dict[str, str | bool]
    warm_up_days: Count
    budget_usd: Amount
    start_at: datetime
    end_at: datetime

    @model_validator(mode="after")
    def check_span(self) -> Self:
        if self.end_at <= self.start_at:
            raise ValueError("backtest end must follow its start")
        return self


class IndicatorsSection(SettingsSection):
    period: Count


class BreakoutSection(SettingsSection):
    range_fraction_min: Fraction
    long_stop_fraction: Fraction
    mid_fraction: Fraction
    short_stop_fraction: Fraction
    stop_fraction_min: Fraction
    stop_fraction_max: Fraction
    positions_max: Count
    target_fractions: tuple[Fraction, Fraction, Fraction]
    lookback_sessions: Count
    signal_bars_max: Count
    trail_atr_multiple: Amount
    trail_bars_min: Count
    scan_minutes: Count
    close_lead_minutes: Count
    confirm_lookback_days: Count
    trail_lookback_days: Count


class OrderTagSection(SettingsSection):
    stop_fraction_scale: Count


class StrategySection(SettingsSection):
    equity_risk_fraction_max: OptionalFraction
    is_paused: bool


class BreakoutVariationSection(StrategySection):
    opening_minutes: Count
    volume_multiple: Amount
    target_multiples: tuple[float, float, float]
    entry_extension_max: OptionalFraction


class DailySection(SettingsSection):
    average_sessions: Count
    exit_rsi_max: Amount


class DailyVariationSection(StrategySection):
    trend_sessions: Count
    adx_min: Amount
    stop_atr_multiple: Amount
    does_heed_earnings: bool
    positions_max: Count


class DailySmaSection(DailyVariationSection):
    trend_sessions_long: Count
    rsi_min: Amount


class DailyTfbSection(DailyVariationSection):
    turnover_sessions: Count
    trend_lag_sessions: Count


class WebSection(SettingsSection):
    base_url: AnyHttpUrl
    session_secret: SigningSecret
    session_ttl_seconds: Count
    heartbeat_timeout_seconds: Count
    signature_window_seconds: Count
    state_body_bytes_max: Count


class ChartTimeframeSection(SettingsSection):
    pad_days: Count
    span_max: Count
    warm_up_days: Count


class DashboardSection(SettingsSection):
    ledger_ttl_seconds: Count
    pulse_ttl_seconds: Count
    chart_ttl_seconds: Count
    chart_cache_max: Count
    levels_lookback_days: Count
    levels_source: Timeframe
    levels_source_bars_max: Count
    levels_range_multiple: Count
    bars_max: Count
    chart_timeframes: dict[ChartTimeframe, ChartTimeframeSection]
    session_source: Timeframe
    session_source_bars_max: Count
    session_source_pages_max: Count
    page_rows_max: Count
    pages_max: Count
    flat_quantity_max: Amount
    equity_daily_period: EquityPeriod
    equity_daily_timeframe: EquityTimeframe
    equity_intraday_period: EquityPeriod
    equity_intraday_timeframe: EquityTimeframe
    sma_lengths: tuple[Count, ...] = Field(min_length=1)
    sma_colors: tuple[Annotated[str, Field(min_length=1)], ...] = Field(min_length=1)
    ledger_max_age_seconds: MaxAge
    chart_max_age_seconds: MaxAge
    levels_max_age_seconds: MaxAge
    strategies_max_age_seconds: MaxAge
    refresh_poll_seconds: Count
    pulse_poll_seconds: Count

    @model_validator(mode="after")
    def check_chart_timeframes(self) -> Self:
        if len(set(self.sma_lengths)) != len(self.sma_lengths):
            raise ValueError("SMA lengths must be distinct")
        if set(self.chart_timeframes) != set(CHART_TIMEFRAMES):
            raise ValueError(f"chart timeframes must be {', '.join(CHART_TIMEFRAMES)}")
        return self


class LoginSection(SettingsSection):
    oauth_client_id: str = Field(min_length=1)
    oauth_client_secret: RequiredSecret
    allowed_emails: frozenset[Annotated[str, AfterValidator(str.casefold)]] = Field(min_length=1)
    timeout: TimeoutSection
