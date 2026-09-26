from pathlib import Path
from typing import Annotated

from pydantic import Field
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from .sections import (
    BacktestSection,
    BarsSection,
    BreakoutSection,
    BreakoutVariationSection,
    BrokerSection,
    CompanySection,
    Daily20SmaSection,
    DailySection,
    DailySmaSection,
    DailyTfbSection,
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
    model_config = SettingsConfigDict(env_nested_delimiter="__", extra="ignore", frozen=True)


class RuleSettings(Settings):
    benchmark_symbol: Symbol
    risk: RiskSection
    universe: UniverseSection
    company: CompanySection
    earnings: EarningsSection
    indicators: IndicatorsSection
    breakout: BreakoutSection
    breakout_5m: BreakoutVariationSection
    breakout_10m: BreakoutVariationSection
    daily: DailySection
    daily_sma: DailySmaSection
    daily_tfb: DailyTfbSection
    daily_20sma: Daily20SmaSection


class SharedSettings(RuleSettings):
    finnhub: FinnhubSection
    broker: BrokerSection
    bars: BarsSection
    redis: RedisSection


class BotSettings(Settings):
    export: ExportSection
    strategies: Annotated[StrategySelection, NoDecode]
    portfolio: PortfolioSection
    backtest: BacktestSection


class WebSettings(Settings):
    requests: RequestSection
    mode: Annotated[Mode, Field(validation_alias="MISE_ENV")]
    web: WebSection
    dashboard: DashboardSection

    @property
    def oauth_redirect_uri(self) -> str:
        return f"{str(self.web.base_url).rstrip('/')}/auth/callback"


class DeploymentSettings(Settings):
    project_root: Path = Field(validation_alias="MISE_PROJECT_ROOT")
    mode: Mode = Field(validation_alias="MISE_ENV")


class LoginSettings(Settings):
    login: LoginSection
