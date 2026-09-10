from typing import Literal

from pydantic import UUID4, AwareDatetime, BaseModel, ConfigDict, Field
from redis import Redis
from redis.asyncio import Redis as AsyncRedis

from .config.settings import RuleSettings
from .config.values import STRATEGY_KEYS, StrategyKey


type EventLevel = Literal["info", "warning", "error"]
type RunStatus = Literal["starting", "running", "stopped", "failed"]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class StateEvent(_StrictModel):
    kind: str = Field(min_length=1, max_length=100)
    occurred_at: AwareDatetime
    level: EventLevel
    message: str = Field(min_length=1, max_length=500)
    strategy_key: StrategyKey | None = None


class State(_StrictModel):
    run_id: UUID4 | None = Field(default=None, exclude=True)
    sequence: int | None = Field(default=None, ge=1, exclude=True)
    status: RunStatus
    strategies: list[StrategyKey] = Field(min_length=1, max_length=len(STRATEGY_KEYS))
    paused: list[StrategyKey] = Field(
        default_factory=list[StrategyKey], max_length=len(STRATEGY_KEYS)
    )
    started_at: AwareDatetime | None = Field(default=None, exclude=True)
    heartbeat_at: AwareDatetime
    configuration: RuleSettings
    events: list[StateEvent]


STATE_KEY = "mt:state"


def publish_state(client: Redis, state: State) -> None:
    client.set(STATE_KEY, state.model_dump_json())


async def read_state(client: AsyncRedis) -> State | None:
    raw = await client.get(STATE_KEY)
    return State.model_validate_json(raw) if raw is not None else None
