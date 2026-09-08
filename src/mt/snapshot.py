from typing import Literal

from pydantic import UUID4, AwareDatetime, BaseModel, ConfigDict, Field

from mt.config.sections import RiskSection
from mt.config.settings import settings
from mt.config.values import STRATEGY_KEYS, StrategyKey
from mt.strategies.base import EventLevel


type RunStatus = Literal["starting", "running", "stopped", "failed"]

STATE_SIGNATURE_SALT = "money-tree.runtime-state.v1"


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class StateEvent(_StrictModel):
    kind: str = Field(min_length=1, max_length=100)
    occurred_at: AwareDatetime
    level: EventLevel
    message: str = Field(min_length=1, max_length=500)
    strategy: StrategyKey | None = None


class StateSnapshot(_StrictModel):
    run_id: UUID4
    sequence: int = Field(ge=1)
    status: RunStatus
    strategies: list[StrategyKey] = Field(min_length=1, max_length=len(STRATEGY_KEYS))
    paused: list[StrategyKey] = Field(
        default_factory=list[StrategyKey], max_length=len(STRATEGY_KEYS)
    )
    started_at: AwareDatetime
    heartbeat_at: AwareDatetime
    configuration: RiskSection
    events: list[StateEvent] = Field(max_length=settings.export.events_max)
