from pathlib import Path
from typing import Annotated, Self

from pydantic import AfterValidator, AnyHttpUrl, Field, model_validator

from .values import (
    Amount,
    BrokerMode,
    Count,
    DataFeedName,
    Fraction,
    MaxAge,
    OptionalFraction,
    RequiredSecret,
    SettingsSection,
    SigningSecret,
)


class BrokerSection(SettingsSection):
    mode: BrokerMode
    api_key: RequiredSecret
    api_secret: RequiredSecret


class PastSection(SettingsSection):
    intraday_feed: DataFeedName
    daily_feed: DataFeedName


class RiskSection(SettingsSection):
    per_day_max: Fraction
    per_trade_max: Fraction
    position_fraction_max: Annotated[float, Field(gt=0, le=0.10)]
    positions_max: Count
    notional_usd_min: Amount
    fractional_orders: bool

    @model_validator(mode="after")
    def validate_limits(self) -> Self:
        if self.per_trade_max > self.per_day_max:
            raise ValueError("risk per trade must not exceed risk per day")
        return self


class ExportSection(SettingsSection):
    url: AnyHttpUrl
    secret: SigningSecret
    interval_seconds: Count


class UniverseSection(SettingsSection):
    cache: Path
    market_cap_usd_min: Amount
    price_usd_min: Amount
    turnover_usd_min: Amount
    past_days: Count


class PortfolioSection(SettingsSection):
    symbols_per_request: Count
    orders_per_request: Count
    preparation_attempts_max: Count
    pending_ttl_minutes: Count


class EarningsSection(SettingsSection):
    block_days: Count
    exit_lead_minutes: Count


class BacktestSection(SettingsSection):
    warm_up_days: Count
    budget_usd: Amount


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
    past_sessions: Count
    signal_candles_max: Count
    trail_atr_multiple: Amount
    trail_bars_min: Count
    scan_minutes: Count
    close_lead_minutes: Count
    confirm_past_days: Count
    trail_past_days: Count


class StrategySection(SettingsSection):
    risk_fraction_max: OptionalFraction
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
    average_lag_sessions: Count


class WebSection(SettingsSection):
    base_url: AnyHttpUrl
    session_secret: SigningSecret
    session_ttl_seconds: Annotated[int, Field(gt=0, le=86_400)]
    heartbeat_timeout_seconds: Count
    signature_window_seconds: Count
    state_body_bytes_max: Count


class DashboardSection(SettingsSection):
    ledger_ttl_seconds: Count
    pulse_ttl_seconds: Count
    chart_ttl_seconds: Count
    chart_cache_max: Count
    levels_past_days: Count
    session_source_bars_max: Count
    session_source_pages_max: Count
    page_rows_max: Count
    pages_max: Count
    sma_lengths: tuple[int, ...] = Field(min_length=1)
    ledger_max_age_seconds: MaxAge
    chart_max_age_seconds: MaxAge
    levels_max_age_seconds: MaxAge
    strategies_max_age_seconds: MaxAge
    refresh_poll_seconds: Count
    pulse_poll_seconds: Count


class LoginSection(SettingsSection):
    railway_oauth_client_id: str = Field(min_length=1)
    railway_oauth_client_secret: RequiredSecret
    allowed_railway_emails: frozenset[Annotated[str, AfterValidator(str.casefold)]] = Field(
        min_length=1
    )
