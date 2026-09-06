from pathlib import Path
from typing import Self

from pydantic import AnyHttpUrl, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .types import (
    STRATEGY_KEYS,
    BrokerMode,
    DataFeedName,
    RequiredSecret,
    RiskLimit,
    SigningSecret,
    StrategyName,
    TradingConfiguration,
    is_strategy_name,
)


class BotSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", frozen=True)

    strategies: str
    alpaca_api_key: RequiredSecret
    alpaca_api_secret: RequiredSecret
    broker_mode: BrokerMode
    alpaca_data_feed: DataFeedName
    alpaca_daily_feed: DataFeedName
    universe_cache: Path
    state_export_url: AnyHttpUrl
    state_export_secret: SigningSecret
    fractional_orders: bool
    risk_per_day_max: RiskLimit
    risk_per_trade_max: RiskLimit
    position_fraction_max: RiskLimit

    @model_validator(mode="after")
    def validate_limits(self) -> Self:
        if self.risk_per_trade_max > self.risk_per_day_max:
            raise ValueError("risk per trade must not exceed risk per day")
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

    @property
    def trading_configuration(self) -> TradingConfiguration:
        return TradingConfiguration(
            fractional_orders=self.fractional_orders,
            position_fraction_max=self.position_fraction_max,
            risk_per_day_max=self.risk_per_day_max,
            risk_per_trade_max=self.risk_per_trade_max,
        )


settings = BotSettings()  # pyright: ignore[reportCallIssue]
