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
    DailySection,
    DailySmaSection,
    DailyTfbSection,
    DashboardSection,
    EarningsSection,
    ExportSection,
    FinnhubSection,
    IndicatorsSection,
    LoginSection,
    OrderTagSection,
    PortfolioSection,
    RequestSection,
    RiskSection,
    ScreenSection,
    WebSection,
)
from .values import Mode, StrategySelection, Symbol


class RuleSettings(BaseSettings):
    model_config = SettingsConfigDict(env_nested_delimiter="__", extra="ignore", frozen=True)

    benchmark_symbol: Symbol
    risk: RiskSection
    screen: ScreenSection
    earnings: EarningsSection
    indicators: IndicatorsSection
    breakout: BreakoutSection
    breakout_5m: BreakoutVariationSection
    breakout_10m: BreakoutVariationSection
    daily: DailySection
    daily_sma: DailySmaSection
    daily_tfb: DailyTfbSection


class SharedSettings(RuleSettings):
    order_tag: OrderTagSection
    finnhub: FinnhubSection


class BotSettings(SharedSettings):
    strategies: Annotated[StrategySelection, NoDecode]
    broker: BrokerSection
    bars: BarsSection
    export: ExportSection
    portfolio: PortfolioSection
    backtest: BacktestSection


class WebSettings(SharedSettings):
    requests: RequestSection
    mode: Annotated[Mode, Field(validation_alias="MISE_ENV")]
    broker: BrokerSection
    bars: BarsSection
    export: ExportSection
    web: WebSection
    dashboard: DashboardSection

    @property
    def oauth_redirect_uri(self) -> str:
        return f"{str(self.web.base_url).rstrip('/')}/auth/callback"


class DeploymentSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", frozen=True)

    project_root: Path = Field(validation_alias="MISE_PROJECT_ROOT")
    mode: Mode = Field(validation_alias="MISE_ENV")


class LoginSettings(BaseSettings):
    model_config = SettingsConfigDict(env_nested_delimiter="__", extra="ignore", frozen=True)

    login: LoginSection


settings = SharedSettings()  # pyright: ignore[reportCallIssue]
