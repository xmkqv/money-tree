from datetime import date
from functools import lru_cache
from importlib import import_module
from typing import Any, cast

from mt.config.settings import settings

from mt.exchange import XNYS


yfinance = cast(Any, import_module("yfinance"))


@lru_cache(maxsize=512)
def earnings_dates(symbol: str) -> tuple[date, ...]:
    values = yfinance.Ticker(symbol).get_earnings_dates(limit=24)
    if values is None:
        return ()
    return tuple(sorted({value.date() for value in values.index}))


def next_earnings(symbol: str, day: date) -> date | None:
    return next((value for value in earnings_dates(symbol) if value >= day), None)


def is_earnings_blocked(symbol: str, day: date) -> bool:
    upcoming = next_earnings(symbol, day)
    return upcoming is not None and 0 <= (upcoming - day).days <= settings.earnings.block_days


def is_earnings_exit_due(symbol: str, day: date) -> bool:
    upcoming = next_earnings(symbol, day)
    if upcoming is None:
        return False
    session = XNYS.date_to_session(upcoming, direction="next")
    return day == XNYS.previous_session(session).date()
