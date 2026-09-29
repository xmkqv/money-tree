import asyncio
from collections.abc import Awaitable, Callable, Hashable

from cachetools import TTLCache


class ReadClosedCacheError(RuntimeError):
    pass


class Cache[Key: Hashable, Value]:
    def __init__(self, ttl_seconds: int, entries_max: int = 1) -> None:
        self._entries: TTLCache[Key, Value] = TTLCache[Key, Value](entries_max, ttl_seconds)
        self._pending: dict[Key, asyncio.Future[Value]] = {}
        self._running: set[asyncio.Future[Value]] = set()
        self._is_closed = False

    async def get_or_build(self, key: Key, build: Callable[[], Awaitable[Value]]) -> Value:
        if self._is_closed:
            raise ReadClosedCacheError("Cache is closed")
        if key in self._entries:
            return self._entries[key]
        if key not in self._pending:
            task = self._pending[key] = asyncio.ensure_future(build())
            self._running.add(task)
            task.add_done_callback(lambda finished: self._finish(key, finished))
        return await asyncio.shield(self._pending[key])

    def get(self, key: Key) -> Value | None:
        return self._entries.get(key)

    def drop(self, key: Key) -> None:
        self._entries.pop(key, None)
        self._pending.pop(key, None)

    async def close(self) -> None:
        self._is_closed = True
        for task in self._running:
            task.cancel()
        await asyncio.gather(*self._running, return_exceptions=True)

    def _finish(self, key: Key, task: asyncio.Future[Value]) -> None:
        self._running.discard(task)
        is_failed = task.cancelled() or task.exception() is not None
        if self._pending.get(key) is task:
            del self._pending[key]
            if not is_failed:
                self._entries[key] = task.result()
