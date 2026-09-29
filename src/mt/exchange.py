from datetime import date, datetime, time

import exchange_calendars
from pandas import DatetimeIndex, Series


CALENDAR_YEARS_AHEAD = 5

XNYS = exchange_calendars.get_calendar(
    "XNYS", end=date(date.today().year + CALENDAR_YEARS_AHEAD, 12, 31)
)
TRADING_ZONE = XNYS.tz


def session_bounds(day: date) -> tuple[datetime, datetime] | None:
    return _bounds(day) if XNYS.is_session(day) else None


def upcoming_session_bounds(day: date) -> tuple[datetime, datetime]:
    return _bounds(XNYS.date_to_session(day, direction="next"))


def session_starts(index: DatetimeIndex) -> DatetimeIndex:
    return _session_stamps(index, XNYS.opens)


def session_ends(index: DatetimeIndex) -> DatetimeIndex:
    return _session_stamps(index, XNYS.closes)


def today() -> date:
    return datetime.now(TRADING_ZONE).date()


def midnight(day: date) -> datetime:
    return datetime.combine(day, time(), TRADING_ZONE)


def _bounds(session: date) -> tuple[datetime, datetime]:
    opens, closes = XNYS.session_open_close(session)
    return (
        opens.tz_convert(TRADING_ZONE).to_pydatetime(),
        closes.tz_convert(TRADING_ZONE).to_pydatetime(),
    )


def _session_stamps(index: DatetimeIndex, table: Series) -> DatetimeIndex:
    sessions = index.tz_convert(TRADING_ZONE).normalize().tz_localize(None)
    return DatetimeIndex(table.reindex(sessions).array).tz_convert(TRADING_ZONE)
