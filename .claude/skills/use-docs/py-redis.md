# redis

redis-py [8.1.0][release] · asyncio API · [connections][connections] · [examples][asyncio]

## client lifetime

```python
import redis.asyncio as redis

# Redis.from_url(url: str, single_connection_client: bool = False,
#                auto_close_connection_pool: bool | None = None, **kwargs) -> Redis
client = redis.from_url("redis://localhost:6379/0", decode_responses=True)
try:
    await client.set("myapp:key", "value", ex=60)
    value = await client.get("myapp:key")  # str | None
finally:
    await client.aclose()  # closes the internally owned pool
```

## pool ownership

```python
# Redis.from_pool(pool) -> Redis; transfers pool ownership to the client
pool = redis.ConnectionPool.from_url("redis://localhost:6379/0")
client = redis.Redis.from_pool(pool)
try:
    await client.ping()
finally:
    await client.aclose()

# Redis(connection_pool=pool); leaves pool ownership with the caller
pool = redis.ConnectionPool.from_url("redis://localhost:6379/0")
first = redis.Redis(connection_pool=pool)
second = redis.Redis(connection_pool=pool)
try:
    await first.set("myapp:key", "value")
    value = await second.get("myapp:key")
finally:
    await first.aclose()
    await second.aclose()
    await pool.aclose()
```

## transactional batch

```python
# pipeline(transaction=True) -> Pipeline
async with client.pipeline(transaction=True) as pipe:
    results = await (
        pipe.set("myapp:first", "a")
        .set("myapp:second", "b")
        .execute()
    )
```

## optimistic update

[WATCH][transactions] detects changes; the loop retries the update.

```python
from redis.exceptions import WatchError

async with client.pipeline(transaction=True) as pipe:
    while True:
        try:
            await pipe.watch("myapp:count")
            value = int(await pipe.get("myapp:count") or 0)
            pipe.multi()
            pipe.set("myapp:count", value + 1)
            await pipe.execute()
            break
        except WatchError:
            continue
```

## bounded lock

```python
# lock(name, timeout=None, sleep=0.1, blocking=True, blocking_timeout=None,
#      thread_local=True, raise_on_release_error=True) -> Lock
async with client.lock("myapp:lock", timeout=30, blocking_timeout=5):
    ...  # protected work completes within the lease
```

## response protocol

```python
# 8.0+: default wire protocol is RESP3; default Python shapes remain RESP2-compatible
client = redis.Redis(protocol=3)  # opts into RESP3-specific response shapes
try:
    await client.ping()
finally:
    await client.aclose()

client = redis.Redis(protocol=2)  # forces RESP2 on the wire
try:
    await client.ping()
finally:
    await client.aclose()
```

## tips

- URL query options are cast and override keyword arguments.
- `decode_responses=True` returns text; the default returns bytes.
- Async clients and caller-owned pools need explicit `aclose()` calls.
- `pipeline(transaction=True)` batches writes; conditional updates also need `watch()`.
- Lock expiry does not stop protected work; `extend()` can renew an owned lease.
- Lock acquisition and release can raise [lock errors][lock].

## refs

[connections]: https://redis.readthedocs.io/en/stable/connections.html
[asyncio]: https://redis.readthedocs.io/en/stable/examples/asyncio_examples.html
[transactions]: https://redis.readthedocs.io/en/stable/advanced_features.html
[lock]: https://redis.readthedocs.io/en/stable/lock.html
[release]: https://pypi.org/project/redis/8.1.0/
