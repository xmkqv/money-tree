from typing import Annotated, Self

from pydantic import AnyHttpUrl, Field, RedisDsn, model_validator

from .values import (
    CHART_TIMEFRAMES,
    Amount,
    BrokerMode,
    ChartTimeframe,
    Count,
    CssToken,
    DataFeedName,
    Email,
    EquityPeriod,
    EquityTimeframe,
    Fraction,
    NonNegative,
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

    @property
    def key_pair(self) -> tuple[str, str]:
        return self.api_key.get_secret_value(), self.api_secret.get_secret_value()

    @property
    def is_paper(self) -> bool:
        return self.mode == "paper"


class FinnhubSection(SettingsSection):
    api_key: RequiredSecret
    timeout: TimeoutSection


class BarsSection(SettingsSection):
    symbols_per_request: Count
    options_per_request: Count
    intraday_feed: DataFeedName
    daily_feed: DataFeedName
    sip_delay_minutes: NonNegative
    trade_max_age_seconds: NonNegative
    timeout: TimeoutSection


class RiskSection(SettingsSection):
    per_day_max: Fraction
    positions_max: Annotated[int, Field(ge=2)]
    notional_usd_min: Amount
    notional_usd_max: Amount
    quantity_decimal_places: Count

    @property
    def strategy_holdings_max(self) -> int:
        return self.positions_max // 2

    @model_validator(mode="after")
    def check_limits(self) -> Self:
        if self.notional_usd_max < self.notional_usd_min:
            raise ValueError("the holding cap must not fall below the smallest tradable notional")
        return self


class RedisSection(SettingsSection):
    url: RedisDsn


class ExportSection(SettingsSection):
    interval_seconds: Count
    events_max: Count
    close_timeout_seconds: Amount


class UniverseSection(SettingsSection):
    price_usd_min: Amount
    turnover_usd_min: Amount
    turnover_sessions: Count
    lookback_days: Count


class PortfolioSection(SettingsSection):
    orders_per_request: Count
    lookback_days: Count
    pending_ttl_minutes: Count
    opening_lead_minutes: Count
    iteration_minutes: Count
    stop_coverage_drift_shares_max: Amount


class CompanySection(SettingsSection):
    profile_cache_max: Count


class CalendarSection(SettingsSection):
    cache_max: Count


class EarningsSection(SettingsSection):
    block_days: Count


class BacktestSection(SettingsSection):
    asset_defaults: dict[str, str | bool]
    warm_up_days: Count
    budget_usd: Amount


class IndicatorsSection(SettingsSection):
    period_bars: Count


class BreakoutSection(SettingsSection):
    range_fraction_min: Fraction
    long_stop_fraction: Fraction
    mid_fraction: Fraction
    short_stop_fraction: Fraction
    stop_fraction_min: Fraction
    stop_fraction_max: Fraction
    target_fractions: tuple[Fraction, Fraction]
    lookback_sessions: Count
    signal_bars_max: Count
    trail_atr_multiple: Amount
    trail_bars_min: Count
    scan_minutes: Count
    close_lead_minutes: Count
    confirm_lookback_days: Count
    trail_lookback_days: Count

    @model_validator(mode="after")
    def check_bands(self) -> Self:
        if self.stop_fraction_max <= self.stop_fraction_min:
            raise ValueError("the stop fractions must rise from their floor to their ceiling")
        if sum(self.target_fractions) >= 1:
            raise ValueError("the target fractions must leave a share to trail")
        return self


class StrategySection(SettingsSection):
    is_paused: bool


class BreakoutVariationSection(StrategySection):
    opening_minutes: Count
    volume_multiple: Amount
    target_multiples: tuple[Amount, Amount, Amount]
    entry_extension_max: Fraction | None

    @model_validator(mode="after")
    def check_targets(self) -> Self:
        first, second, third = self.target_multiples
        if not first < second < third:
            raise ValueError("target multiples must rise")
        return self


class DailySection(SettingsSection):
    average_sessions: Count
    exit_rsi_max: Amount


class DailyVariationSection(StrategySection):
    trend_sessions: Count
    adx_min: Amount
    holdings_max: Count


class DailyAtrSection(DailyVariationSection):
    stop_atr_multiple: Amount


class DailySmaSection(DailyAtrSection):
    trend_sessions_long: Count
    rsi_min: Amount


class Daily20SmaSection(DailyVariationSection):
    trend_sessions_long: Count
    rsi_min: Amount
    rsi_max: Amount
    market_cap_usd_min: Amount
    entry_minutes: Count
    stop_fraction: Fraction
    breakeven_gain: Fraction
    target_gains: tuple[Fraction, Fraction]
    target_fractions: tuple[Fraction, Fraction]
    trail_atr_multiple: Amount
    trail_hours: Count
    trail_lookback_days: Count

    @model_validator(mode="after")
    def check_bands(self) -> Self:
        if self.rsi_max <= self.rsi_min:
            raise ValueError("the RSI band must rise from its floor to its ceiling")
        if self.target_gains[1] <= self.target_gains[0]:
            raise ValueError("target gains must rise")
        if sum(self.target_fractions) >= 1:
            raise ValueError("the target fractions must leave a share to trail")
        return self


class DailyTfbSection(DailyAtrSection):
    turnover_sessions: Count
    trend_lag_sessions: Count


class RequestSection(SettingsSection):
    web_reads_per_minute: Count
    web_market_data_per_minute: Count
    web_concurrency_max: Count
    pause_seconds: Count


class WebSection(SettingsSection):
    base_url: AnyHttpUrl
    login_secret: SigningSecret
    login_ttl_seconds: Count
    heartbeat_timeout_seconds: Count

    @property
    def oauth_redirect_uri(self) -> str:
        return f"{str(self.base_url).rstrip('/')}/auth/callback"


class ChartTimeframeSection(SettingsSection):
    pad_days: Count
    span_days_max: Count
    warm_up_days: Count


class DashboardSection(SettingsSection):
    history_overlap_days: Count
    ledger_ttl_seconds: Count
    snapshot_ttl_seconds: Count
    chart_ttl_seconds: Count
    chart_cache_max: Count
    name_ttl_seconds: Count
    name_cache_max: Count
    levels_lookback_days: Count
    levels_source: Timeframe
    levels_source_bars_max: Count
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
    equity_daily_ttl_seconds: Count
    sma_lengths: tuple[Count, ...] = Field(min_length=1)
    sma_colors: tuple[CssToken, ...] = Field(min_length=1)
    ledger_max_age_seconds: NonNegative
    chart_max_age_seconds: NonNegative
    levels_max_age_seconds: NonNegative
    strategies_max_age_seconds: NonNegative
    refresh_poll_seconds: Count
    snapshot_poll_seconds: Count

    @model_validator(mode="after")
    def check_dashboard(self) -> Self:
        if len(set(self.sma_lengths)) != len(self.sma_lengths):
            raise ValueError("SMA lengths must be distinct")
        if set(self.chart_timeframes) != set(CHART_TIMEFRAMES):
            raise ValueError(f"chart timeframes must be {', '.join(CHART_TIMEFRAMES)}")
        return self


class LoginSection(SettingsSection):
    oauth_client_id: str = Field(min_length=1)
    oauth_client_secret: RequiredSecret
    allowed_emails: frozenset[Email] = Field(min_length=1)
    timeout: TimeoutSection
