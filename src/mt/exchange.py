from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import exchange_calendars
from pandas import DatetimeIndex, Series


CALENDAR_AHEAD_YEARS = 5
ZONE_NAME = "America/New_York"

XNYS = exchange_calendars.get_calendar(
    "XNYS", end=date(datetime.now(ZoneInfo(ZONE_NAME)).year + CALENDAR_AHEAD_YEARS, 12, 31)
)
TRADING_ZONE = XNYS.tz


def session_bounds(session_on: date) -> tuple[datetime, datetime] | None:
    return _bounds(session_on) if XNYS.is_session(session_on) else None


def upcoming_session_bounds(session_on: date) -> tuple[datetime, datetime]:
    return _bounds(upcoming_session_on(session_on))


def upcoming_session_on(session_on: date) -> date:
    return XNYS.date_to_session(session_on, direction="next").date()


def previous_session_on(session_on: date) -> date:
    return XNYS.date_to_session(session_on - timedelta(days=1), direction="previous").date()


def session_starts(index: DatetimeIndex) -> DatetimeIndex:
    return _session_stamps(index, XNYS.opens)


def session_ends(index: DatetimeIndex) -> DatetimeIndex:
    return _session_stamps(index, XNYS.closes)


def today_on() -> date:
    return datetime.now(TRADING_ZONE).date()


def midnight(session_on: date) -> datetime:
    return datetime.combine(session_on, time(), TRADING_ZONE)


def _bounds(session_on: date) -> tuple[datetime, datetime]:
    opens, closes = XNYS.session_open_close(session_on)
    return (
        opens.tz_convert(TRADING_ZONE).to_pydatetime(),
        closes.tz_convert(TRADING_ZONE).to_pydatetime(),
    )


def _session_stamps(index: DatetimeIndex, table: Series) -> DatetimeIndex:
    sessions = index.tz_convert(TRADING_ZONE).normalize().tz_localize(None)
    return DatetimeIndex(table.reindex(sessions).array).tz_convert(TRADING_ZONE)
