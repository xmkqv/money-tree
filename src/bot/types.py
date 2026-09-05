from collections.abc import Iterable
from typing import Annotated, Literal, TypeIs

from pydantic import UUID4, AwareDatetime, BaseModel, ConfigDict, Field, SecretStr


type RiskLimit = Annotated[float, Field(gt=0, le=1)]
type RequiredSecret = Annotated[SecretStr, Field(min_length=1)]
type SigningSecret = Annotated[SecretStr, Field(min_length=32)]
type RunStatus = Literal["starting", "running", "stopped", "failed"]
type EventLevel = Literal["info", "warning", "error"]
type StrategyName = Literal["orb", "sma", "tfb_50", "orb_momentum"]
type DataFeedName = Literal["sip", "delayed_sip", "iex"]

STATE_SIGNATURE_SALT = "money-tree.runtime-state.v1"
POSITIONS_MAX = 10
POSITION_FRACTION_CAP = 0.10
EVENTS_MAX = 50
STRATEGY_LABELS: dict[StrategyName, str] = {
    "orb": "ORB (5-minute)",
    "sma": "Momentum (SMA)",
    "tfb_50": "TFB-50",
    "orb_momentum": "ORB (10-minute)",
}
STRATEGY_SHORT_LABELS: dict[StrategyName, str] = {
    "orb": "ORB5",
    "orb_momentum": "ORB10",
    "sma": "Momentum SMA",
    "tfb_50": "TFB-50",
}
PAUSED_STRATEGIES: frozenset[StrategyName] = frozenset({"orb_momentum"})


def is_strategy_name(value: str) -> TypeIs[StrategyName]:
    return value in STRATEGY_LABELS


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


class StateEvent(_StrictModel):
    kind: str = Field(min_length=1, max_length=100)
    occurred_at: AwareDatetime
    level: EventLevel
    message: str = Field(min_length=1, max_length=500)
    strategy: str | None = Field(default=None, min_length=1, max_length=100)


class StateSnapshot(_StrictModel):
    run_id: UUID4
    sequence: int = Field(ge=1)
    status: RunStatus
    strategies: list[str] = Field(min_length=1, max_length=len(STRATEGY_LABELS))
    paused: list[str] = Field(default_factory=list, max_length=len(STRATEGY_LABELS))
    started_at: AwareDatetime
    heartbeat_at: AwareDatetime
    configuration: TradingConfiguration
    events: list[StateEvent] = Field(max_length=EVENTS_MAX)
