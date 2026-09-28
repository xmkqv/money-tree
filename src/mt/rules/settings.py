from pathlib import Path
from typing import Annotated, Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from .sections import (
    AllocationBaaSection,
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
    EdgarSection,
    ExportSection,
    FinnhubSection,
    IndicatorsSection,
    IntradayMimSection,
    LoginSection,
    PortfolioSection,
    QualityGpSection,
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
    breakout_15m: BreakoutVariationSection
    daily: DailySection
    daily_sma: DailySmaSection
    daily_tfb: DailyTfbSection
    daily_20sma: Daily20SmaSection
    intraday_mim: IntradayMimSection
    allocation_baa: AllocationBaaSection
    quality_gp: QualityGpSection

    @model_validator(mode="after")
    def check_strategy_holdings(self) -> Self:
        capped = (
            self.daily_sma,
            self.daily_tfb,
            self.daily_20sma,
            self.intraday_mim,
            self.allocation_baa,
            self.quality_gp,
        )
        if any(section.holdings_max > self.risk.strategy_holdings_max for section in capped):
            raise ValueError("a strategy holding cap exceeds the risk holdings cap")
        return self


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
    edgar: EdgarSection


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
