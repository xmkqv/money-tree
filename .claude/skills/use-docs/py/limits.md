# [limits][limits:docs]

5.8.0 · [async API][limits:async] · [reference][limits:api] · [changes][limits:changelog]

## backend from a URI

```py
from limits.storage import storage_from_string
from limits.aio.strategies import MovingWindowRateLimiter

# storage_from_string(storage_string: str, **options: float | str | bool)
#     -> limits.storage.Storage | limits.aio.storage.Storage
storage = storage_from_string(
    "async+redis://localhost:6379/0",
    implementation="redispy",
)
limiter = MovingWindowRateLimiter(storage)
```

## explicit async client

```py
from limits.aio.storage import RedisStorage

# RedisStorage(uri: str, wrap_exceptions: bool = False,
#              implementation: Literal['redispy', 'coredis', 'valkey'] = 'coredis',
#              key_prefix: str = 'LIMITS', **options)
storage = RedisStorage(
    "async+redis://localhost:6379/0",
    implementation="redispy",
    key_prefix="myapp",
)
limiter = MovingWindowRateLimiter(storage)
```

## consume a weighted allowance

```py
from limits import parse

item = parse("100/minute")

# async hit(item, *identifiers, cost=1) -> bool
allowed = await limiter.hit(item, "user", "123", cost=2)
if allowed:
    ...  # handle the request
```

## inspect without consuming

```py
# async test(item, *identifiers, cost=1) -> bool
available = await limiter.test(item, "user", "123", cost=2)

# async get_window_stats(item, *identifiers) -> WindowStats
stats = await limiter.get_window_stats(item, "user", "123")
reset_time, remaining = stats.reset_time, stats.remaining
```

## refs

[limits:docs]: https://limits.readthedocs.io/en/stable/

[limits:api]: https://limits.readthedocs.io/en/stable/api.html
    Time as seconds since the Epoch when this window will be reset

[limits:async]: https://limits.readthedocs.io/en/stable/async.html

[limits:storage]: https://limits.readthedocs.io/en/stable/storage.html

[limits:changelog]: https://limits.readthedocs.io/en/stable/changelog.html
