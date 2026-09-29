# [cachetools][cachetools:docs]

7.2.0 · Python 3.10+ · [changes][cachetools:changelog]

## expiring bounded cache

[`TTLCache(maxsize, ttl, timer=time.monotonic, getsizeof=None)`][cachetools:docs] → mapping; expired items behave as absent.

```py
from cachetools import TTLCache

cache: TTLCache[str, bytes] = TTLCache(maxsize=256, ttl=60.0)
cache["key"] = b"value"
value = cache.get("key")             # None once expired
expired = cache.expire()             # [(key, value), …] removed now
cache.pop("key", None)
```

## per-item lifetime

`TLRUCache(maxsize, ttu, timer=…)`; `ttu(key, value, now) -> expires_at` on the same clock as `timer`.

```py
from cachetools import TLRUCache


def ttu(key, value, now):
    return now + (5.0 if value.is_partial else 300.0)


cache = TLRUCache(maxsize=128, ttu=ttu)
```

## eviction policies

`LRUCache`, `LFUCache`, `FIFOCache`, `RRCache` share `Cache(maxsize, getsizeof=None)`; `getsizeof` bounds by weight.

```py
from cachetools import LRUCache

by_bytes = LRUCache(maxsize=10_000_000, getsizeof=len)
by_count = LRUCache(maxsize=1024)
by_count.popitem()                   # evicts the least recently used pair
```

## compute on miss

Override `Cache.__missing__(key)`; the returned value is stored by the subclass.

```py
from cachetools import LRUCache


class Loader(LRUCache):
    def __missing__(self, key):
        value = self[key] = load(key)
        return value


loader = Loader(maxsize=512)
value = loader["key"]
```

## memoize a function

`cached(cache, key=hashkey, lock=None, condition=None, info=False)`; the wrapper exposes `cache`, `cache_key`, `cache_lock`, `cache_clear()`.

```py
from threading import RLock

from cachetools import TTLCache, cached
from cachetools.keys import hashkey

lock = RLock()


@cached(TTLCache(maxsize=128, ttl=30), key=lambda user, *, refresh=False: hashkey(user), lock=lock)
def fetch(user, *, refresh=False): ...
```

## stampede protection and statistics

`condition=Condition()` makes concurrent callers of one key wait for a single computation; `info=True` adds `cache_info()`.

```py
from threading import Condition

from cachetools import LRUCache, cached


@cached(LRUCache(maxsize=64), condition=Condition(), info=True)
def expensive(arg): ...


expensive(1)
hits, misses, maxsize, currsize = expensive.cache_info()
expensive.cache_clear()
```

## per-instance method cache

`cachedmethod(cache, key=methodkey, lock=None, condition=None, info=False)`; `cache` is a callable taking `self`.

```py
from operator import attrgetter
from threading import RLock

from cachetools import TTLCache, cachedmethod


class Client:
    def __init__(self):
        self._cache = TTLCache(maxsize=32, ttl=10)
        self._lock = RLock()

    @cachedmethod(attrgetter("_cache"), lock=attrgetter("_lock"))
    def get(self, path): ...
```

## key functions

`hashkey(*args, **kwargs)`, `typedkey` (distinguishes `1` from `1.0`), `methodkey` / `typedmethodkey` drop `self`.

```py
from cachetools import cached
from cachetools.keys import hashkey, typedkey


@cached(cache, key=lambda symbol, day, **_: hashkey(symbol, day))
def profile(symbol, day, timeout=None): ...


key = typedkey(1) != typedkey(1.0)
```

## functools-compatible decorators

`cachetools.func.ttl_cache(maxsize=128, ttl=600, timer=time.monotonic, typed=False)` is thread-safe and stampede-safe.

```py
from cachetools.func import lru_cache, ttl_cache


@ttl_cache(maxsize=None, ttl=30)
def rates(): ...


@lru_cache(maxsize=256)
def parse(text): ...


rates.cache_info()
rates.cache_clear()
```

## injectable clock for tests

`timer` is any zero-argument float callable; `cache.timer` returns it.

```py
from cachetools import TTLCache


class Clock:
    now = 0.0

    def __call__(self):
        return self.now


clock = Clock()
cache = TTLCache(maxsize=4, ttl=10, timer=clock)
cache["a"] = 1
clock.now = 11.0
assert "a" not in cache
```

## refs

[cachetools:docs]: https://cachetools.readthedocs.io/en/latest/
    Please be aware that all these classes are *not* thread-safe.

[cachetools:changelog]: https://github.com/tkem/cachetools/blob/master/CHANGELOG.rst
    @cachetools.cached(cache=None) is deprecated

[cachetools:asyncio]: https://github.com/hephex/asyncache
    asyncache provides helpers to use cachetools with async code
