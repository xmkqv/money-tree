import asyncio
from collections.abc import Awaitable, Callable, Hashable

from cachetools import TTLCache


class Cache[Key: Hashable, Value]:
    def __init__(self, ttl_seconds: int, entries_max: int = 1) -> None:
        self._entries: TTLCache[Key, Value] = TTLCache[Key, Value](entries_max, ttl_seconds)
        self._pending: dict[Key, asyncio.Future[Value]] = {}
        self._running: set[asyncio.Future[Value]] = set()
        self._closed = False

    async def get_or_build(self, key: Key, build: Callable[[], Awaitable[Value]]) -> Value:
        if self._closed:
            raise RuntimeError("Cache is closed")
        value = self.fresh(key)
        if value is not None:
            return value
        if key not in self._pending:
            task = self._pending[key] = asyncio.ensure_future(build())
            self._running.add(task)
            task.add_done_callback(lambda finished: self._finish(key, finished))
        return await asyncio.shield(self._pending[key])

    def _finish(self, key: Key, task: asyncio.Future[Value]) -> None:
        self._running.discard(task)
        failed = task.cancelled() or task.exception() is not None
        if self._pending.get(key) is task:
            del self._pending[key]
            if not failed:
                self._entries[key] = task.result()

    async def close(self) -> None:
        self._closed = True
        for task in self._running:
            task.cancel()
        await asyncio.gather(*self._running, return_exceptions=True)

    def fresh(self, key: Key) -> Value | None:
        return self._entries.get(key)

    def drop(self, key: Key) -> None:
        self._entries.pop(key, None)
        self._pending.pop(key, None)
