import asyncio
import logging
import math
import re
import time
from email.utils import parsedate_to_datetime

import httpx
from limits import RateLimitItemPerMinute
from limits.aio.storage import MemoryStorage
from limits.aio.strategies import MovingWindowRateLimiter
from pydantic import BaseModel, ConfigDict

from mt.config.sections import TimeoutSection


logger = logging.getLogger(__name__)


class Payload(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


def http_timeout(timeout: TimeoutSection) -> httpx.Timeout:
    return httpx.Timeout(
        connect=timeout.connect_seconds,
        read=timeout.read_seconds,
        write=timeout.write_seconds,
        pool=timeout.pool_seconds,
    )


class RequestTransport(httpx.AsyncHTTPTransport):
    def __init__(self, allowance: int, concurrency: asyncio.Semaphore, pause_seconds: int) -> None:
        super().__init__(retries=0)
        self._allowance = RateLimitItemPerMinute(allowance)
        self._limiter = MovingWindowRateLimiter(MemoryStorage())
        self._concurrency = concurrency
        self._pause_seconds = pause_seconds
        self._resume_at = 0.0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        while True:
            if time.time() < self._resume_at:
                return self._limited()
            if not await self._limiter.test(self._allowance):
                reset_at = (await self._limiter.get_window_stats(self._allowance)).reset_time
                await asyncio.sleep(max(0, reset_at - time.time()))
                continue
            async with self._concurrency:
                if time.time() < self._resume_at:
                    return self._limited()
                if not await self._limiter.hit(self._allowance):
                    continue
                started = time.monotonic()
                response = None
                try:
                    response = await super().handle_async_request(request)
                    await response.aread()
                    if response.status_code == 429:
                        self._resume_at = max(
                            self._resume_at, retry_at(response, self._pause_seconds)
                        )
                        response.headers["Retry-After"] = str(
                            math.ceil(self._resume_at - time.time())
                        )
                    return response
                finally:
                    if response is not None:
                        await response.aclose()
                    logger.info(
                        "endpoint=%s operation=%s status=%s duration=%.3f "
                        "attempts=1 remaining=%s reset=%s",
                        re.sub(r"(/stocks|/orders)/[^/]+", r"\1/{id}", request.url.path),
                        request.method,
                        response.status_code if response else "failed",
                        time.monotonic() - started,
                        response.headers.get("X-RateLimit-Remaining") if response else None,
                        response.headers.get("X-RateLimit-Reset") if response else None,
                    )

    def _limited(self) -> httpx.Response:
        return httpx.Response(
            429, headers={"Retry-After": str(max(1, math.ceil(self._resume_at - time.time())))}
        )


def retry_at(response: httpx.Response, fallback_seconds: int) -> float:
    now = time.time()
    times: list[float] = []
    retry = response.headers.get("Retry-After")
    reset = response.headers.get("X-RateLimit-Reset")
    for value, relative in ((retry, True), (reset, False)):
        if value is None:
            continue
        try:
            number = float(value)
            stamp = now + number if relative else number
        except ValueError:
            try:
                stamp = parsedate_to_datetime(value).timestamp()
            except (ValueError, TypeError, OverflowError):
                continue
        if math.isfinite(stamp) and stamp > now:
            times.append(stamp)
    return max(times, default=now + fallback_seconds)
