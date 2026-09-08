from datetime import UTC, date, datetime
from typing import Any, cast

import exchange_calendars
from pandas import DatetimeIndex


XNYS = exchange_calendars.get_calendar("XNYS")
TRADING_ZONE = XNYS.tz


def session_bounds(day: date) -> tuple[datetime, datetime] | None:
    return _bounds(day) if XNYS.is_session(day) else None


def upcoming_session_bounds(day: date) -> tuple[datetime, datetime]:
    return _bounds(XNYS.date_to_session(day, direction="next"))


def trading_time(timestamp: str) -> datetime:
    return datetime.fromisoformat(timestamp).astimezone(TRADING_ZONE)


def session_starts(index: DatetimeIndex) -> DatetimeIndex:
    return _session_stamps(index, cast(Any, XNYS).opens)


def session_ends(index: DatetimeIndex) -> DatetimeIndex:
    return _session_stamps(index, cast(Any, XNYS).closes)


def _bounds(session: Any) -> tuple[datetime, datetime]:
    opens = cast(Any, XNYS.session_first_minute(session)).astimezone(TRADING_ZONE)
    closes = cast(Any, XNYS.session_close(session)).astimezone(TRADING_ZONE)
    return cast(datetime, opens.to_pydatetime()), cast(datetime, closes.to_pydatetime())


def _session_stamps(index: DatetimeIndex, table: Any) -> DatetimeIndex:
    sessions = cast(Any, index).tz_convert(TRADING_ZONE).normalize().tz_localize(None)
    stamps = DatetimeIndex(table.reindex(sessions).to_numpy(), tz=UTC)
    return cast(DatetimeIndex, cast(Any, stamps).tz_convert(TRADING_ZONE))
