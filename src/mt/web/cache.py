import asyncio
import logging
from collections.abc import Awaitable, Callable

from cachetools import TTLCache


logger = logging.getLogger(__name__)


class Cache[Value]:
    def __init__(self, ttl_seconds: int, entries_max: int = 1) -> None:
        self._entries: TTLCache[str, Value] = TTLCache[str, Value](entries_max, ttl_seconds)
        self._pending: dict[str, asyncio.Future[Value]] = {}
        self._running: set[asyncio.Future[Value]] = set()
        self._closed = False

    async def get_or_build(self, key: str, build: Callable[[], Awaitable[Value]]) -> Value:
        if self._closed:
            raise RuntimeError("Cache is closed")
        value = self.fresh(key)
        logger.debug("cache outcome=%s", "hit" if value is not None else "miss")
        if value is not None:
            return value
        if key not in self._pending:
            task = self._pending[key] = asyncio.ensure_future(build())
            self._running.add(task)
            task.add_done_callback(lambda finished: self._finish(key, finished))
        return await asyncio.shield(self._pending[key])

    def _finish(self, key: str, task: asyncio.Future[Value]) -> None:
        self._running.discard(task)
        failed = task.cancelled() or task.exception() is not None
        if self._pending.get(key) is task:
            del self._pending[key]
            if not failed:
                self.store(key, task.result())

    async def close(self) -> None:
        self._closed = True
        for task in self._running:
            task.cancel()
        await asyncio.gather(*self._running, return_exceptions=True)

    def fresh(self, key: str) -> Value | None:
        return self._entries.get(key)

    def store(self, key: str, value: Value) -> None:
        self.drop(key)
        self._entries[key] = value

    def drop(self, key: str) -> None:
        self._entries.pop(key, None)
        self._pending.pop(key, None)
