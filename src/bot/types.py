from typing import Annotated, Literal, Self, TypeIs

from pydantic import (
    UUID4,
    AnyHttpUrl,
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    SecretStr,
    model_validator,
)


def parse_none(value: object) -> object:
    return None if value == "none" else value


type RiskLimit = Annotated[float, Field(gt=0, le=1)]
type Symbol = Annotated[str, Field(min_length=1, max_length=12, pattern=r"^[A-Z][A-Z.]*$")]
type RequiredSecret = Annotated[SecretStr, Field(min_length=1)]
type SigningSecret = Annotated[SecretStr, Field(min_length=32)]
type RunStatus = Literal["starting", "running", "stopped", "failed"]
type EventLevel = Literal["info", "warning", "error"]
type StrategyName = Literal["breakout_5m", "breakout_10m", "daily_sma", "daily_tfb"]
type DataFeedName = Literal["sip", "delayed_sip", "iex"]
type BrokerMode = Literal["live", "paper"]
type Direction = Literal[-1, 1]
type OptionalRiskLimit = Annotated[RiskLimit | None, BeforeValidator(parse_none)]

STATE_SIGNATURE_SALT = "money-tree.runtime-state.v1"
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


class SettingsSection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class BrokerSection(SettingsSection):
    mode: BrokerMode
    data_feed: DataFeedName
    daily_feed: DataFeedName
    api_key: RequiredSecret
    api_secret: RequiredSecret


class RiskSection(SettingsSection):
    per_day_max: RiskLimit
    per_trade_max: RiskLimit
    position_fraction_max: Annotated[float, Field(gt=0, le=0.10)]
    positions_max: Annotated[int, Field(gt=0)]
    notional_usd_min: Annotated[float, Field(gt=0)]
    fractional_orders: bool

    @model_validator(mode="after")
    def validate_limits(self) -> Self:
        if self.per_trade_max > self.per_day_max:
            raise ValueError("risk per trade must not exceed risk per day")
        return self


class ExportSection(SettingsSection):
    url: AnyHttpUrl
    secret: SigningSecret
    interval_seconds: Annotated[int, Field(gt=0)]


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
    configuration: RiskSection
    events: list[StateEvent] = Field(max_length=EVENTS_MAX)
