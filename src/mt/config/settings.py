from typing import Annotated, Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from mt.strategies.keys import STRATEGY_KEYS, StrategyName, is_strategy_name

from .sections import (
    BacktestSection,
    BreakoutSection,
    BreakoutVariationSection,
    BrokerSection,
    DailySection,
    DailySmaSection,
    DailyTfbSection,
    DashboardSection,
    EarningsSection,
    ExportSection,
    IndicatorsSection,
    LoginSection,
    PastSection,
    PortfolioSection,
    RiskSection,
    UniverseSection,
    WebSection,
)
from .values import Mode, Symbol


class BotSettings(BaseSettings):
    model_config = SettingsConfigDict(env_nested_delimiter="__", extra="ignore", frozen=True)

    strategies: str
    benchmark_symbol: Symbol
    broker: BrokerSection
    past: PastSection
    risk: RiskSection
    export: ExportSection
    universe: UniverseSection
    portfolio: PortfolioSection
    earnings: EarningsSection
    backtest: BacktestSection
    indicators: IndicatorsSection
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


class WebSettings(BaseSettings):
    model_config = SettingsConfigDict(env_nested_delimiter="__", extra="ignore", frozen=True)

    mode: Annotated[Mode, Field(validation_alias="MISE_ENV")]
    benchmark_symbol: Symbol
    broker: BrokerSection
    past: PastSection
    risk: RiskSection
    export: ExportSection
    web: WebSection
    dashboard: DashboardSection

    @property
    def railway_oauth_redirect_uri(self) -> str:
        return f"{str(self.web.base_url).rstrip('/')}/auth/callback"


class LoginSettings(BaseSettings):
    model_config = SettingsConfigDict(env_nested_delimiter="__", extra="ignore", frozen=True)

    login: LoginSection


settings = BotSettings()  # pyright: ignore[reportCallIssue]
