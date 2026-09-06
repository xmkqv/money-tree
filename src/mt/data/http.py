import httpx

from mt.config.sections import TimeoutSection


def http_timeout(timeout: TimeoutSection) -> httpx.Timeout:
    return httpx.Timeout(
        connect=timeout.connect_seconds,
        read=timeout.read_seconds,
        write=timeout.write_seconds,
        pool=timeout.pool_seconds,
    )
