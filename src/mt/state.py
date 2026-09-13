from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
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
    status: RunStatus
    strategies: list[StrategyKey] = Field(min_length=1, max_length=len(STRATEGY_KEYS))
    paused: list[StrategyKey] = Field(
        default_factory=list[StrategyKey], max_length=len(STRATEGY_KEYS)
    )
    heartbeat_at: AwareDatetime
    rules: RuleSettings
    events: list[StateEvent]


STATE_KEY = "mt:state"


def publish_state(client: Redis, state: State) -> None:
    client.set(STATE_KEY, state.model_dump_json())


async def read_state(client: AsyncRedis) -> State | None:
    raw = await client.get(STATE_KEY)
    return State.model_validate_json(raw) if raw is not None else None
