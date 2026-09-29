# [exchange-calendars][exchange-calendars:docs]

4.13.2 · Python 3.10-3.14 · pandas 2.x and 3.x

```py
import exchange_calendars as xcals
import pandas as pd
from exchange_calendars import errors
from exchange_calendars.exchange_calendar import ExchangeCalendar
```

[`xcals.get_calendar(name, start?, end?, side?)`][exchange-calendars:calendars] → `ExchangeCalendar`; instances are cached per argument set.

```py
calendar: ExchangeCalendar = xcals.get_calendar("XNYS")  # sessions span 20 years back to 1 year ahead
bounded = xcals.get_calendar("XNYS", start="2000-01-03", end="2030-12-31", side="both")

zone = calendar.tz  # ZoneInfo of the exchange
first, last = calendar.first_session, calendar.last_session  # tz-naive midnight Timestamps
has_break = calendar.has_break
early = calendar.early_closes  # DatetimeIndex of sessions that close early
```

[`is_session(date)` / `date_to_session(date, direction)`][exchange-calendars:sessions] → `bool` / session `pd.Timestamp`; a date is a tz-naive midnight.

```py
def session_for(day: str, direction: str = "next") -> pd.Timestamp:
    if calendar.is_session(day):
        return pd.Timestamp(day)
    return calendar.date_to_session(day, direction=direction)  # "next" | "previous" | "none"


following = calendar.next_session("2025-11-28")
prior = calendar.previous_session("2025-11-28")
shifted = calendar.session_offset("2025-11-28", -5)  # negative counts back
```

[`minute_to_session(minute, direction)`][exchange-calendars:minutes] → session `pd.Timestamp`; resolves an instant to the session it belongs to.

```py
now = pd.Timestamp.now(tz="UTC")
session = calendar.minute_to_session(now, direction="previous")  # closed hours → last session
same_day = calendar.minute_to_session(now, direction="none")  # raises ValueError when closed
sessions = calendar.minutes_to_sessions(pd.DatetimeIndex([now]))  # every minute must be trading
```

[`sessions_in_range(start, end)` / `sessions_window(session, count)`][exchange-calendars:sessions] → `pd.DatetimeIndex` of sessions.

```py
span = calendar.sessions_in_range("2025-01-01", "2025-03-31")  # inclusive both ends
recent = calendar.sessions_window("2025-11-28", -20)  # 20 sessions ending at the anchor
ahead = calendar.sessions_window("2025-11-28", 5)  # 5 sessions starting at the anchor
count = calendar.sessions_distance("2025-01-01", "2025-03-31")  # sessions in the span
```

[`session_open` / `session_close` / `session_open_close`][exchange-calendars:calendars] → UTC `pd.Timestamp`; convert for local wall time.

```py
opened, closed = calendar.session_open_close("2025-11-28")
local_open = opened.tz_convert(calendar.tz).to_pydatetime()
local_close = closed.tz_convert(calendar.tz).to_pydatetime()  # 13:00 on an early close

open_series: pd.Series = calendar.opens  # index: sessions, dtype: datetime64[ns, UTC]
close_series: pd.Series = calendar.closes
window = calendar.sessions_in_range("2025-11-24", "2025-11-28")
local_closes = close_series.loc[window].dt.tz_convert(calendar.tz)
```

[`is_trading_minute(minute)` / `is_open_on_minute(minute)`][exchange-calendars:minutes] → `bool`; `side` decides whether the open and close minutes count.

```py
minute = pd.Timestamp("2025-11-28 14:30", tz="UTC")
trading = calendar.is_trading_minute(minute)  # left side: open yes, close no
open_now = calendar.is_open_on_minute(minute, ignore_breaks=False)
at_instant = calendar.is_open_at_time(minute, side="both")  # any resolution, seconds included

following_open = calendar.next_open(minute)
following_close = calendar.next_close(minute)
prior_close = calendar.previous_close(minute)
```

[`session_minutes(session)` / `minutes_in_range(start, end)`][exchange-calendars:minutes] → UTC `pd.DatetimeIndex` of one-minute trading minutes.

```py
minutes = calendar.session_minutes("2025-11-28")
between = calendar.minutes_in_range(
    pd.Timestamp("2025-11-28 15:00", tz="UTC"), pd.Timestamp("2025-11-28 16:00", tz="UTC")
)
last_hour = calendar.minutes_window(minutes[-1], -60)  # 60 minutes ending at the anchor
first, last = calendar.session_first_last_minute("2025-11-28")
```

[`trading_index(start, end, period, ...)`][exchange-calendars:trading-index] → `pd.IntervalIndex` or `pd.DatetimeIndex` of bar spans.

```py
bars = calendar.trading_index("2025-11-24", "2025-11-28", "1h", force_close=True)  # IntervalIndex
starts = calendar.trading_index("2025-11-28", "2025-11-28", "5min", intervals=False, closed="left")
aligned = calendar.trading_index("2025-11-28", "2025-11-28", "30min", align="30min")
daily = calendar.trading_index("2025-11-24", "2025-11-28", "1D")  # dates only

lefts = bars.left.tz_convert(calendar.tz)
```

[`schedule`][exchange-calendars:calendars] → `pd.DataFrame` indexed by session with UTC `open`, `break_start`, `break_end`, `close`.

```py
schedule: pd.DataFrame = calendar.schedule
month = schedule.loc["2025-11-01":"2025-11-30", ["open", "close"]]
local = month.apply(lambda column: column.dt.tz_convert(calendar.tz))
length = (month["close"] - month["open"]).rename("length")  # half days are shorter
```

[`errors`][exchange-calendars:errors] → `ValueError` subclasses for out-of-range dates, minutes and offsets.

```py
def safe_session(day: str) -> pd.Timestamp | None:
    try:
        return calendar.date_to_session(day, direction="previous")
    except errors.DateOutOfBounds:  # before first or after last session
        return None
    except ValueError:  # `direction="none"` on a non-session
        return None


try:
    calendar.session_offset(calendar.last_session, 1)
except errors.RequestedSessionOutOfBounds:
    pass
```

## refs

[exchange-calendars:docs]: https://github.com/gerrymanoim/exchange_calendars
    Sessions are now timezone-naive (previously UTC).
    Default calendar 'side' for all calendars is now "left"

[exchange-calendars:calendars]: https://github.com/gerrymanoim/exchange_calendars/blob/master/docs/tutorials/calendar_methods.ipynb
    If timezone naive then will be assumed as representing UTC.
    Schedule columns now have timezone set as UTC

[exchange-calendars:sessions]: https://github.com/gerrymanoim/exchange_calendars/blob/master/docs/tutorials/sessions.ipynb
    Positive to return window of sessions from `session`
    Negative to return window of sessions to `session`.
    If `date` is timezone aware.

[exchange-calendars:minutes]: https://github.com/gerrymanoim/exchange_calendars/blob/master/docs/tutorials/minutes.ipynb
    by default minutes are closed on the left side
    Minutes during breaks are not considered trading minutes.
    Get session corresponding with a trading or break minute.

[exchange-calendars:trading-index]: https://github.com/gerrymanoim/exchange_calendars/blob/master/docs/tutorials/trading_index.ipynb
    If False, defines right side of this period after the session close.
    If `period` is one day ("1D") then `start` must be passed as a date.

[exchange-calendars:errors]: https://github.com/gerrymanoim/exchange_calendars/blob/master/exchange_calendars/errors.py
    "left" - Session open and break_start are trading minutes.
