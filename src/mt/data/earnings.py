from datetime import date, timedelta
from functools import lru_cache

from mt.config.settings import settings
from mt.exchange import XNYS

from .finnhub import earnings_dates


@lru_cache(maxsize=settings.earnings.calendar_cache_max)
def _calendar(day: date) -> dict[str, date]:
    return earnings_dates(day, day + timedelta(days=settings.earnings.block_days))


def is_earnings_blocked(symbol: str, day: date) -> bool:
    return symbol in _calendar(day)


def is_earnings_exit_due(symbol: str, day: date) -> bool:
    upcoming = _calendar(day).get(symbol)
    if upcoming is None:
        return False
    session = XNYS.date_to_session(upcoming, direction="next")
    return day == XNYS.previous_session(session).date()
