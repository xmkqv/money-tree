from collections.abc import Iterable
from typing import Annotated, Literal, Self, cast

from pydantic import (
    UUID4,
    AnyHttpUrl,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


type RiskLimit = Annotated[float, Field(gt=0, le=1)]
type RequiredSecret = Annotated[SecretStr, Field(min_length=1)]
type SigningSecret = Annotated[SecretStr, Field(min_length=32)]
type RunStatus = Literal["starting", "running", "stopped", "failed"]
type EventLevel = Literal["info", "warning", "error"]
type StrategyName = Literal["noop", "orb5", "sma", "tfb_50", "orb10", "orb15"]
type DataFeedName = Literal["sip", "delayed_sip", "iex"]

STATE_SIGNATURE_SALT = "money-tree.runtime-state.v1"
POSITIONS_MAX = 10
POSITION_FRACTION_CAP_MAX = 0.10
STRATEGY_LABELS: dict[StrategyName, str] = {
    "noop": "No-op",
    "orb5": "ORB (5-minute)",
    "sma": "Momentum (SMA)",
    "tfb_50": "TFB-50",
    "orb10": "ORB (10-minute)",
    "orb15": "ORB (15-minute)",
}
PAUSED_STRATEGIES: frozenset[StrategyName] = frozenset({"orb10"})


def active_strategies(selected: Iterable[StrategyName]) -> list[StrategyName]:
    return [name for name in selected if name not in PAUSED_STRATEGIES]


def published_roster(selected: Iterable[StrategyName]) -> tuple[list[str], list[str]]:
    names = list(selected)
    return (
        [STRATEGY_LABELS[name] for name in names],
        [STRATEGY_LABELS[name] for name in names if name in PAUSED_STRATEGIES],
    )


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class TradingConfiguration(_StrictModel):
    fractional_orders: bool
    position_fraction_max: RiskLimit
    risk_per_day_max: RiskLimit
    risk_per_trade_max: RiskLimit


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", frozen=True)

    strategies: str
    alpaca_api_key: RequiredSecret
    alpaca_api_secret: RequiredSecret
    alpaca_is_paper: bool
    alpaca_data_feed: DataFeedName
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
        unknown = set(values).difference(STRATEGY_LABELS)
        if unknown:
            raise ValueError(f"unknown strategies: {', '.join(sorted(unknown))}")
        return self

    @property
    def strategy_names(self) -> list[StrategyName]:
        values = [item.strip() for item in self.strategies.split(",")]
        return cast(list[StrategyName], [value for value in values if value in STRATEGY_LABELS])

    @property
    def trading_configuration(self) -> TradingConfiguration:
        return TradingConfiguration(
            fractional_orders=self.fractional_orders,
            position_fraction_max=self.position_fraction_max,
            risk_per_day_max=self.risk_per_day_max,
            risk_per_trade_max=self.risk_per_trade_max,
        )


class RuntimeEvent(_StrictModel):
    kind: str = Field(min_length=1, max_length=100)
    occurred_at: AwareDatetime
    level: EventLevel
    message: str = Field(min_length=1, max_length=500)
    strategy: str | None = Field(default=None, min_length=1, max_length=100)


class RuntimeSnapshot(_StrictModel):
    run_id: UUID4
    sequence: int = Field(ge=1)
    status: RunStatus
    strategies: list[str] = Field(min_length=1, max_length=6)
    paused: list[str] = Field(default_factory=list, max_length=6)
    started_at: AwareDatetime
    heartbeat_at: AwareDatetime
    configuration: TradingConfiguration
    events: list[RuntimeEvent] = Field(max_length=50)
