from redis import Redis
from redis.asyncio import Redis as AsyncRedis

from .snapshot import StateSnapshot


STATE_KEY = "mt:state"


def publish_state(client: Redis, snapshot: StateSnapshot) -> None:
    client.set(STATE_KEY, snapshot.model_dump_json())


async def read_state(client: AsyncRedis) -> StateSnapshot | None:
    raw = await client.get(STATE_KEY)
    return StateSnapshot.model_validate_json(raw) if raw is not None else None
