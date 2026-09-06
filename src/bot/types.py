from typing import Annotated, Literal, TypeIs

from pydantic import UUID4, AwareDatetime, BaseModel, ConfigDict, Field, SecretStr


type RiskLimit = Annotated[float, Field(gt=0, le=1)]
type RequiredSecret = Annotated[SecretStr, Field(min_length=1)]
type SigningSecret = Annotated[SecretStr, Field(min_length=32)]
type RunStatus = Literal["starting", "running", "stopped", "failed"]
type EventLevel = Literal["info", "warning", "error"]
type StrategyName = Literal["breakout_5m", "breakout_10m", "daily_sma", "daily_tfb"]
type DataFeedName = Literal["sip", "delayed_sip", "iex"]
type BrokerMode = Literal["live", "paper"]
type Direction = Literal[-1, 1]

STATE_SIGNATURE_SALT = "money-tree.runtime-state.v1"
POSITIONS_MAX = 10
POSITION_FRACTION_CAP = 0.10
EVENTS_MAX = 50
STRATEGY_KEYS: tuple[StrategyName, ...] = (
    "breakout_5m",
    "breakout_10m",
    "daily_sma",
    "daily_tfb",
)


def no_strategies() -> list[StrategyName]:
    return []


def is_strategy_name(value: str) -> TypeIs[StrategyName]:
    return value in STRATEGY_KEYS


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class TradingConfiguration(_StrictModel):
    fractional_orders: bool
    position_fraction_max: RiskLimit
    risk_per_day_max: RiskLimit
    risk_per_trade_max: RiskLimit


class StateEvent(_StrictModel):
    kind: str = Field(min_length=1, max_length=100)
    occurred_at: AwareDatetime
    level: EventLevel
    message: str = Field(min_length=1, max_length=500)
    strategy: StrategyName | None = None


class StateSnapshot(_StrictModel):
    run_id: UUID4
    sequence: int = Field(ge=1)
    status: RunStatus
    strategies: list[StrategyName] = Field(min_length=1, max_length=len(STRATEGY_KEYS))
    paused: list[StrategyName] = Field(default_factory=no_strategies, max_length=len(STRATEGY_KEYS))
    started_at: AwareDatetime
    heartbeat_at: AwareDatetime
    configuration: TradingConfiguration
    events: list[StateEvent] = Field(max_length=EVENTS_MAX)
