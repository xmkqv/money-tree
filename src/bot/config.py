from pathlib import Path
from typing import Annotated, Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .types import (
    STRATEGY_KEYS,
    BrokerSection,
    ExportSection,
    OptionalRiskLimit,
    RiskSection,
    SettingsSection,
    StrategyName,
    Symbol,
    is_strategy_name,
)


type Count = Annotated[int, Field(gt=0)]
type Amount = Annotated[float, Field(gt=0)]
type Fraction = Annotated[float, Field(gt=0, le=1)]


class UniverseSection(SettingsSection):
    cache: Path
    market_cap_usd_min: Amount
    price_usd_min: Amount
    turnover_usd_min: Amount
    history_days: Count


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


class IndicatorSection(SettingsSection):
    period: Count


class BreakoutSection(SettingsSection):
    range_fraction_min: Fraction
    long_stop_fraction: Fraction
    mid_fraction: Fraction
    short_stop_fraction: Fraction
    stop_fraction_min: Fraction
    stop_fraction_max: Fraction
    positions_max: Count
    history_sessions: Count
    signal_candles_max: Count
    trail_atr_multiple: Amount
    trail_bars_min: Count
    scan_minutes: Count
    close_lead_minutes: Count
    confirm_history_days: Count
    trail_history_days: Count


class BreakoutVariationSection(SettingsSection):
    opening_minutes: Count
    volume_multiple: Amount
    target_multiples: tuple[float, float, float]
    entry_extension_max: OptionalRiskLimit
    risk_fraction_max: OptionalRiskLimit
    is_paused: bool


class DailySection(SettingsSection):
    average_sessions: Count
    exit_rsi_max: Amount


class DailySmaSection(SettingsSection):
    trend_sessions: Count
    trend_sessions_long: Count
    rsi_min: Amount
    adx_min: Amount
    stop_atr_multiple: Amount
    does_heed_earnings: bool
    risk_fraction_max: OptionalRiskLimit
    positions_max: Count
    is_paused: bool


class DailyTfbSection(SettingsSection):
    trend_sessions: Count
    turnover_sessions: Count
    adx_min: Amount
    average_lag_sessions: Count
    stop_atr_multiple: Amount
    does_heed_earnings: bool
    risk_fraction_max: Fraction
    positions_max: Count
    is_paused: bool


class BotSettings(BaseSettings):
    model_config = SettingsConfigDict(env_nested_delimiter="__", extra="ignore", frozen=True)

    strategies: str
    benchmark_symbol: Symbol
    broker: BrokerSection
    risk: RiskSection
    export: ExportSection
    universe: UniverseSection
    portfolio: PortfolioSection
    earnings: EarningsSection
    backtest: BacktestSection
    indicators: IndicatorSection
    breakout: BreakoutSection
    breakout_5m: BreakoutVariationSection
    breakout_10m: BreakoutVariationSection
    daily: DailySection
    daily_sma: DailySmaSection
    daily_tfb: DailyTfbSection

    @model_validator(mode="after")
    def validate_strategies(self) -> Self:
        values = [value.strip() for value in self.strategies.split(",") if value.strip()]
        if not values:
            raise ValueError("STRATEGIES must select at least one strategy")
        if len(values) != len(set(values)):
            raise ValueError("STRATEGIES must not contain duplicates")
        unknown = set(values).difference(STRATEGY_KEYS)
        if unknown:
            raise ValueError(f"unknown strategies: {', '.join(sorted(unknown))}")
        return self

    @property
    def strategy_names(self) -> list[StrategyName]:
        values = [item.strip() for item in self.strategies.split(",")]
        return [value for value in values if is_strategy_name(value)]


settings = BotSettings()  # pyright: ignore[reportCallIssue]
