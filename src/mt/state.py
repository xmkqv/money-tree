from typing import Annotated, Literal

from pydantic import AfterValidator, AwareDatetime, BaseModel, ConfigDict, Field
from redis import Redis
from redis.asyncio import Redis as AsyncRedis

from mt.rules.bot import settings as bot_settings
from mt.rules.settings import RuleSettings
from mt.rules.values import STRATEGY_KEYS, StrategyKey, check_distinct


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
    strategies: Annotated[
        list[StrategyKey],
        AfterValidator(check_distinct),
        Field(min_length=1, max_length=len(STRATEGY_KEYS)),
    ]
    paused: list[StrategyKey] = Field(max_length=len(STRATEGY_KEYS))
    heartbeat_at: AwareDatetime
    rules: RuleSettings
    events: list[StateEvent] = Field(max_length=bot_settings.export.events_max)


STATE_KEY = "mt:state"


def publish_state(client: Redis, state: State) -> None:
    client.set(STATE_KEY, state.model_dump_json())


async def read_state(client: AsyncRedis) -> State | None:
    raw = await client.get(STATE_KEY)
    return State.model_validate_json(raw) if raw is not None else None
