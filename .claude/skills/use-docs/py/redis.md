# [redis-py][redis:docs]

[8.1.0][redis:release] · asyncio API · [connections][redis:connections] · [retry][redis:retry] · [examples][redis:asyncio-examples]

## resilient async client

```py
import redis.asyncio as redis
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialWithJitterBackoff
from redis.exceptions import ConnectionError, TimeoutError

# Redis.from_url(url, **kwargs) -> Redis; keyword arguments feed the connection
# from_url without `retry`: NoBackoff, 0 retries; Redis(host=...) alone defaults to 10 retries
client = redis.from_url(
    "redis://localhost:6379/0",
    decode_responses=True,  # str in, str out; no manual bytes decoding
    socket_connect_timeout=2.0,
    socket_timeout=5.0,  # per-command read/write bound; 8.x defaults both timeouts to 5
    health_check_interval=30,  # PING idle connections before reuse
    retry=Retry(ExponentialWithJitterBackoff(base=0.05, cap=1.0), retries=3),
    retry_on_error=[ConnectionError, TimeoutError],  # added to the retry's supported errors
)
```

## owned lifetime

```py
from contextlib import asynccontextmanager

# Redis is an async context manager; __aexit__ awaits aclose() and closes the owned pool
@asynccontextmanager
async def lifespan(app):
    async with redis.from_url("redis://localhost:6379/0", decode_responses=True) as client:
        yield {"store": client}  # one client per process; commands share its pool
```

## write with expiry and guard

```py
# set(name, value, ex=None, px=None, nx=False, xx=False, keepttl=False, get=False, ...)
stored = await client.set("ns:lock", "owner", ex=30, nx=True)  # True | None
await client.set("ns:state", payload, keepttl=True)  # overwrite, keep the TTL
previous = await client.set("ns:state", payload, get=True)  # returns the old value
```

## typed read

```py
from pydantic import BaseModel

class Doc(BaseModel):
    version: int

# decode_responses=True → str | None; skip raw.decode()
raw = await client.get("ns:doc")
doc = Doc.model_validate_json(raw) if raw is not None else None
await client.set("ns:doc", Doc(version=2).model_dump_json())
```

## sync client for a background thread

```py
import redis as sync_redis
from redis.exceptions import RedisError

# a thread owns its own sync client; never share a client between the loop and a thread
with sync_redis.Redis.from_url("redis://localhost:6379/0") as client:
    while not stopping.wait(interval):
        try:
            client.set("ns:heartbeat", payload)  # RedisError covers connection and response failures
        except RedisError as error:
            log.warning("publish failed: %s", type(error).__name__)
```

## transactional batch

```py
# pipeline(transaction=True) -> Pipeline; commands buffer until execute()
async with client.pipeline(transaction=True) as pipe:
    results = await (
        pipe.set("ns:first", "a")
        .expire("ns:first", 60)
        .incr("ns:count")
        .execute()  # MULTI/EXEC; one result per command
    )
```

## optimistic update

[WATCH][redis:transactions] detects changes; the loop retries the update.

```py
from redis.exceptions import WatchError

async with client.pipeline(transaction=True) as pipe:
    while True:
        try:
            await pipe.watch("ns:count")
            value = int(await pipe.get("ns:count") or 0)
            pipe.multi()  # back to buffered mode
            pipe.set("ns:count", value + 1)
            await pipe.execute()
            break
        except WatchError:
            continue
```

## bounded lock

```py
# lock(name, timeout=None, sleep=0.1, blocking=True, blocking_timeout=None,
#      thread_local=True, raise_on_release_error=True) -> Lock
async with client.lock("ns:lock", timeout=30, blocking_timeout=5):
    ...  # protected work completes within the lease
```

## pub/sub with a poll timeout

```py
async with client.pubsub() as pubsub:
    await pubsub.subscribe("ns:events")
    while True:
        message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
        if message is not None:
            handle(message["data"])  # dict: type, channel, data
```

## pool ownership and protocol

```py
# Redis.from_pool(pool) transfers pool ownership; Redis(connection_pool=pool) does not
pool = redis.ConnectionPool.from_url("redis://localhost:6379/0", max_connections=20)
first = redis.Redis(connection_pool=pool)
second = redis.Redis(connection_pool=pool)
try:
    await first.set("ns:key", "value")
finally:
    await first.aclose()
    await second.aclose()
    await pool.aclose()  # caller closes a pool it owns

# 8.0+: RESP3 is the default wire protocol; protocol=2 forces RESP2
legacy = redis.Redis(protocol=2)
```

## refs

[redis:docs]: https://redis.readthedocs.io/en/stable/

[redis:connections]: https://redis.readthedocs.io/en/stable/connections.html
    In the case of conflicting arguments, querystring arguments always win

[redis:retry]: https://redis.readthedocs.io/en/stable/retry.html

[redis:asyncio-examples]: https://redis.readthedocs.io/en/stable/examples/asyncio_examples.html

[redis:transactions]: https://redis.readthedocs.io/en/stable/advanced_features.html
    the entire transaction will be canceled and a WatchError will be raised
    It is not safe to pass PubSub or Pipeline objects between threads.

[redis:lock]: https://redis.readthedocs.io/en/stable/lock.html

[redis:release]: https://pypi.org/project/redis/8.1.0/
