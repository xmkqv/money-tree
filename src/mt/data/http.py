import httpx
from pydantic import BaseModel, ConfigDict

from mt.config.sections import TimeoutSection


class Payload(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


def http_timeout(timeout: TimeoutSection) -> httpx.Timeout:
    return httpx.Timeout(
        connect=timeout.connect_seconds,
        read=timeout.read_seconds,
        write=timeout.write_seconds,
        pool=timeout.pool_seconds,
    )
