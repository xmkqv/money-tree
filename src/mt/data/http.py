import asyncio
import logging
import math
import re
import time
from collections.abc import Mapping
from datetime import datetime
from email.utils import parsedate_to_datetime
from http import HTTPStatus

import httpx2
from limits import RateLimitItemPerMinute
from limits.aio.storage import MemoryStorage
from limits.aio.strategies import MovingWindowRateLimiter
from pydantic import BaseModel, ConfigDict

from mt.rules.sections import TimeoutSection


class Payload(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True, validate_by_name=True)


class ExceedPagesError(httpx2.HTTPError):
    pass


logger = logging.getLogger(__name__)


async def get_bytes(
    client: httpx2.AsyncClient, path: str, params: Mapping[str, object] | None = None
) -> bytes:
    query = {
        key: value.isoformat() if isinstance(value, datetime) else str(value)
        for key, value in (params or {}).items()
        if value is not None
    }
    response = await client.get(path, params=query)
    return response.raise_for_status().content


def http_timeout(timeout: TimeoutSection) -> httpx2.Timeout:
    return httpx2.Timeout(
        connect=timeout.connect_seconds,
        read=timeout.read_seconds,
        write=timeout.write_seconds,
        pool=timeout.pool_seconds,
    )


class RequestTransport(httpx2.AsyncHTTPTransport):
    def __init__(
        self, requests_per_minute: int, concurrency: asyncio.Semaphore, pause_seconds: int
    ) -> None:
        super().__init__()
        self._allowance = RateLimitItemPerMinute(requests_per_minute)
        self._limiter = MovingWindowRateLimiter(MemoryStorage())
        self._concurrency = concurrency
        self._pause_seconds = pause_seconds
        self._resume_at = 0.0

    async def handle_async_request(self, request: httpx2.Request) -> httpx2.Response:
        if time.time() < self._resume_at:
            return self._limited()
        while not await self._limiter.hit(self._allowance):
            reset_at = (await self._limiter.get_window_stats(self._allowance)).reset_time
            await asyncio.sleep(max(0, reset_at - time.time()))
        async with self._concurrency:
            if time.time() < self._resume_at:
                return self._limited()
            started_at = time.monotonic()
            response = None
            try:
                response = await super().handle_async_request(request)
                await response.aread()
                if response.status_code == HTTPStatus.TOO_MANY_REQUESTS:
                    self._resume_at = max(self._resume_at, _retry_at(response, self._pause_seconds))
                    response.headers["Retry-After"] = str(math.ceil(self._resume_at - time.time()))
                return response
            finally:
                if response is not None:
                    await response.aclose()
                logger.info(
                    "endpoint=%s operation=%s status=%s duration=%.3f remaining=%s reset=%s",
                    re.sub(r"(/orders|/assets)/[^/]+", r"\1/{id}", request.url.path),
                    request.method,
                    response.status_code if response else "failed",
                    time.monotonic() - started_at,
                    response.headers.get("X-RateLimit-Remaining") if response else None,
                    response.headers.get("X-RateLimit-Reset") if response else None,
                )

    def _limited(self) -> httpx2.Response:
        return httpx2.Response(
            HTTPStatus.TOO_MANY_REQUESTS,
            headers={"Retry-After": str(max(1, math.ceil(self._resume_at - time.time())))},
        )


def _retry_at(response: httpx2.Response, fallback_seconds: int) -> float:
    now = time.time()
    times: list[float] = []
    retry = response.headers.get("Retry-After")
    reset = response.headers.get("X-RateLimit-Reset")
    for value, relative in ((retry, True), (reset, False)):
        if value is None:
            continue
        try:
            number = float(value)
            retry_at = now + number if relative else number
        except ValueError:
            try:
                retry_at = parsedate_to_datetime(value).timestamp()
            except ValueError, TypeError, OverflowError:
                continue
        if math.isfinite(retry_at) and retry_at > now:
            times.append(retry_at)
    return max(times, default=now + fallback_seconds)
