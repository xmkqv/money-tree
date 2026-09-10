# limits

5.8.0 · [async API][async] · [reference][api] · [changes][changelog]

## backend from a URI

```python
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

```python
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

```python
from limits import parse

item = parse("100/minute")

# async hit(item, *identifiers, cost=1) -> bool
allowed = await limiter.hit(item, "user", "123", cost=2)
if allowed:
    ...  # handle the request
```

## inspect without consuming

```python
# async test(item, *identifiers, cost=1) -> bool
available = await limiter.test(item, "user", "123", cost=2)

# async get_window_stats(item, *identifiers) -> WindowStats
stats = await limiter.get_window_stats(item, "user", "123")
reset_time, remaining = stats.reset_time, stats.remaining
```

## tips

- Async storage URIs use `async+`; a plain `redis://` URI selects synchronous storage.
- [Redis schemes][storage]: `async+redis`, `async+rediss`, `async+redis+unix`.
- Valkey has the corresponding three `async+valkey` schemes.
- `RedisStorage` defaults to `coredis`; `implementation="redispy"` selects redis-py.
- The selected client package must be installed.
- Matching items, identifiers, backend and key prefix share a rate limit.
- `test()` reserves nothing; `hit()` decides whether an allowance can be consumed.
- `WindowStats.reset_time` is a Unix timestamp; `remaining` counts available units.

## refs

[api]: https://limits.readthedocs.io/en/stable/api.html
[async]: https://limits.readthedocs.io/en/stable/async.html
[storage]: https://limits.readthedocs.io/en/stable/storage.html
[changelog]: https://limits.readthedocs.io/en/stable/changelog.html
