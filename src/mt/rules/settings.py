from pathlib import Path
from typing import Annotated, Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from .sections import (
    BacktestSection,
    BarsSection,
    BreakoutSection,
    BreakoutVariationSection,
    BrokerSection,
    CalendarSection,
    CompanySection,
    Daily20SmaSection,
    DailySection,
    DailySmaSection,
    DailyTfbSection,
    DailyVariationSection,
    DashboardSection,
    EarningsSection,
    ExportSection,
    FinnhubSection,
    IndicatorsSection,
    LoginSection,
    PortfolioSection,
    RedisSection,
    RequestSection,
    RiskSection,
    UniverseSection,
    WebSection,
)
from .values import Mode, StrategySelection, Symbol


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_nested_delimiter="__", extra="ignore", frozen=True, env_parse_none_str="none"
    )


class ModeSettings(Settings):
    mode: Mode = Field(validation_alias="MISE_ENV")


class RuleSettings(Settings):
    benchmark_symbol: Symbol
    risk: RiskSection
    universe: UniverseSection
    earnings: EarningsSection
    indicators: IndicatorsSection
    breakout: BreakoutSection
    breakout_5m: BreakoutVariationSection
    breakout_10m: BreakoutVariationSection
    breakout_15m: BreakoutVariationSection
    daily: DailySection
    daily_sma: DailySmaSection
    daily_tfb: DailyTfbSection
    daily_20sma: Daily20SmaSection

    @model_validator(mode="after")
    def check_strategy_holdings(self) -> Self:
        capped = [section for _, section in self if isinstance(section, DailyVariationSection)]
        if any(section.holdings_max > self.risk.strategy_holdings_max for section in capped):
            raise ValueError("a strategy holding cap exceeds the risk holdings cap")
        return self


class SharedSettings(RuleSettings):
    finnhub: FinnhubSection
    company: CompanySection
    calendar: CalendarSection
    broker: BrokerSection
    bars: BarsSection
    redis: RedisSection


class BotSettings(Settings):
    export: ExportSection
    strategies: Annotated[StrategySelection, NoDecode]
    portfolio: PortfolioSection
    backtest: BacktestSection


class WebSettings(ModeSettings):
    requests: RequestSection
    web: WebSection
    dashboard: DashboardSection


class DeploymentSettings(ModeSettings):
    project_root: Path = Field(validation_alias="MISE_PROJECT_ROOT")


class LoginSettings(Settings):
    login: LoginSection
