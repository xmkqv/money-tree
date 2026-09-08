from typing import Annotated

from pydantic import Field
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

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
    FinnhubSection,
    IndicatorsSection,
    LoginSection,
    PastSection,
    PortfolioSection,
    RiskSection,
    ScreenSection,
    WebSection,
)
from .values import Mode, StrategySelection, Symbol


class BotSettings(BaseSettings):
    model_config = SettingsConfigDict(env_nested_delimiter="__", extra="ignore", frozen=True)

    strategies: Annotated[StrategySelection, NoDecode]
    benchmark_symbol: Symbol
    broker: BrokerSection
    finnhub: FinnhubSection
    past: PastSection
    risk: RiskSection
    export: ExportSection
    screen: ScreenSection
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


class WebSettings(BaseSettings):
    model_config = SettingsConfigDict(env_nested_delimiter="__", extra="ignore", frozen=True)

    mode: Annotated[Mode, Field(validation_alias="MISE_ENV")]
    benchmark_symbol: Symbol
    broker: BrokerSection
    finnhub: FinnhubSection
    past: PastSection
    risk: RiskSection
    export: ExportSection
    web: WebSection
    dashboard: DashboardSection

    @property
    def oauth_redirect_uri(self) -> str:
        return f"{str(self.web.base_url).rstrip('/')}/auth/callback"


class LoginSettings(BaseSettings):
    model_config = SettingsConfigDict(env_nested_delimiter="__", extra="ignore", frozen=True)

    login: LoginSection


settings = BotSettings()  # pyright: ignore[reportCallIssue]
