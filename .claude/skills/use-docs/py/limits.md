# [limits][limits:docs]

5.8.0 · [strategies][limits:strategies] · [async API][limits:async] · [storage][limits:storage] · [reference][limits:api]

## strategy choice

```py
from limits.aio.strategies import (
    FixedWindowRateLimiter,  # one counter per key; cheapest; bursts at window edges
    MovingWindowRateLimiter,  # timestamp log; exact; memory grows with the limit
    SlidingWindowCounterRateLimiter,  # two weighted counters; approximates the log
)
# every limiter shares: hit, test, get_window_stats, clear
# a strategy the storage cannot back raises NotImplementedError at construction
```

## in-process storage

```py
from limits.storage import storage_from_string
from limits.aio.storage import MemoryStorage

# storage_from_string(storage_string, **options) picks the class by URI scheme
storage = storage_from_string("async+memory://")  # async variant; "memory://" is sync
same = MemoryStorage()  # explicit form; supports all three strategies
limiter = MovingWindowRateLimiter(storage)  # counters live in this process only
```

## limit items

```py
from limits import RateLimitItemPerMinute, RateLimitItemPerSecond, parse, parse_many

# RateLimitItem*(amount, multiples=1, namespace="LIMITER")
per_minute = RateLimitItemPerMinute(100)
per_ten_seconds = RateLimitItemPerSecond(5, multiples=10)
parsed = parse("100/minute")
layers = parse_many("5/second; 100/minute")  # list[RateLimitItem]; separators ; , |
```

## layered check

```py
# hit() consumes; a rejected layer must not leave the other layers charged
async def admit(limiter, layers, *identifiers) -> bool:
    for item in layers:
        if not await limiter.test(item, *identifiers):
            return False
    return all([await limiter.hit(item, *identifiers) for item in layers])
```

## consume a weighted allowance

```py
# async hit(item, *identifiers, cost=1) -> bool; identifiers scope the counter
allowed = await limiter.hit(item, "user", "123", cost=2)
# async test(item, *identifiers, cost=1) -> bool; read-only
available = await limiter.test(item, "user", "123", cost=2)
```

## wait until admitted

```py
import asyncio, time

# WindowStats(reset_time: float epoch seconds, remaining: int)
while not await limiter.hit(item):
    stats = await limiter.get_window_stats(item)
    await asyncio.sleep(max(0.0, stats.reset_time - time.time()))
```

## retry-after from window stats

```py
import math, time

if not await limiter.hit(item, *identifiers):
    stats = await limiter.get_window_stats(item, *identifiers)
    retry_after = max(1, math.ceil(stats.reset_time - time.time()))
    headers = {"Retry-After": str(retry_after)}  # reject instead of sleeping
```

## shared backend from a URI

```py
from limits.storage import storage_from_string
from limits.aio.storage import RedisStorage

storage = storage_from_string("async+redis://localhost:6379/0", implementation="redispy")
# RedisStorage(uri, wrap_exceptions=False, implementation='coredis'|'redispy'|'valkey',
#              key_prefix='LIMITS', **options)
explicit = RedisStorage("async+redis://localhost:6379/0", implementation="redispy", key_prefix="app")
healthy = await storage.check()  # bool; probes the backend
await limiter.clear(item, "user", "123")  # forget one key
```

## refs

[limits:docs]: https://limits.readthedocs.io/en/stable/

[limits:strategies]: https://limits.readthedocs.io/en/stable/strategies.html
    Burst traffic that bypasses the rate limit may occur at window boundaries.

[limits:api]: https://limits.readthedocs.io/en/stable/api.html
    Time as seconds since the Epoch when this window will be reset

[limits:async]: https://limits.readthedocs.io/en/stable/async.html

[limits:storage]: https://limits.readthedocs.io/en/stable/storage.html

[limits:changelog]: https://limits.readthedocs.io/en/stable/changelog.html
