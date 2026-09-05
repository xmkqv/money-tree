from collections.abc import Iterable
from typing import Annotated, Literal, Self

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
# Nothing is paused. A strategy named here is loaded and manages whatever it
# already holds, but opens nothing new.
PAUSED_STRATEGIES: frozenset[StrategyName] = frozenset()
# Names a strategy used to answer to. The roster is an environment variable held
# outside this repository, so renaming a strategy in code alone leaves the bot
# refusing a value it accepted yesterday — and refusing it while reading its
# settings, before it can report why. Old names keep resolving, so a roster that
# has not caught up costs a warning rather than the run.
STRATEGY_ALIASES: dict[str, StrategyName] = {
    "orb": "orb5",
    "orb_momentum": "orb10",
}


def resolve_strategy(name: str) -> StrategyName | None:
    """The name this strategy goes by now, or None if it goes by no name at all."""
    if name in STRATEGY_LABELS:
        return name
    return STRATEGY_ALIASES.get(name)


def resolve_roster(values: Iterable[str]) -> tuple[list[StrategyName], dict[str, StrategyName]]:
    """A roster read as current names, alongside the renamed entries it used.

    Rosters are resolved here and nowhere else, so everything downstream — the
    pause list, the labels the bot publishes, the composer — only ever sees the
    name a strategy goes by now.
    """
    names: list[StrategyName] = []
    renamed: dict[str, StrategyName] = {}
    for value in values:
        resolved = resolve_strategy(value)
        if resolved is None:
            continue
        names.append(resolved)
        if value != resolved:
            renamed[value] = resolved
    return names, renamed


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
        values = self._selected_strategies()
        if not values:
            raise ValueError("STRATEGIES must select at least one strategy")
        unknown = {value for value in values if resolve_strategy(value) is None}
        if unknown:
            raise ValueError(f"unknown strategies: {', '.join(sorted(unknown))}")
        # Duplicates are counted after resolution, so "orb,orb5" is the one
        # strategy twice rather than two names that merely look different.
        names, _ = resolve_roster(values)
        if len(names) != len(set(names)):
            raise ValueError("STRATEGIES must not contain duplicates")
        return self

    def _selected_strategies(self) -> list[str]:
        return [value.strip() for value in self.strategies.split(",") if value.strip()]

    @property
    def strategy_names(self) -> list[StrategyName]:
        names, _ = resolve_roster(self._selected_strategies())
        return names

    @property
    def renamed_strategies(self) -> dict[str, StrategyName]:
        """Entries in STRATEGIES that are answering to an old name."""
        _, renamed = resolve_roster(self._selected_strategies())
        return renamed

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
