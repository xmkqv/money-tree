import asyncio
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable


class Cache[Value]:
    def __init__(self, ttl_seconds: int, entries_max: int = 1) -> None:
        self._ttl = ttl_seconds
        self._entries_max = entries_max
        self._entries: OrderedDict[str, tuple[float, Value]] = OrderedDict()
        self._lock = asyncio.Lock()

    async def get_or_build(self, key: str, build: Callable[[], Awaitable[Value]]) -> Value:
        value = self.fresh(key)
        if value is not None:
            return value
        async with self._lock:
            value = self.fresh(key)
            if value is None:
                value = await build()
                self.store(key, value)
        return value

    def fresh(self, key: str) -> Value | None:
        entry = self._entries.get(key)
        if entry is None or time.monotonic() - entry[0] > self._ttl:
            return None
        self._entries.move_to_end(key)
        return entry[1]

    def store(self, key: str, value: Value) -> None:
        self._entries[key] = (time.monotonic(), value)
        self._entries.move_to_end(key)
        while len(self._entries) > self._entries_max:
            self._entries.popitem(last=False)

    def drop(self, key: str) -> None:
        self._entries.pop(key, None)
