from datetime import UTC, date, datetime, timedelta
from datetime import time as dtime
from typing import Any, TypedDict, cast

from pandas import DataFrame, DatetimeIndex, Timedelta

from mt.config.settings import settings
from mt.data.alpaca import Bar
from mt.exchange import TRADING_ZONE, session_starts
from mt.frames import regular_session
from mt.indicators import latest_atr


class BarRow(TypedDict):
    t: str
    o: float
    h: float
    l: float  # noqa: E741
    c: float
    v: float


class TimeframeRules(TypedDict):
    bar: str
    pad_days: int
    span_max: int
    warmup_days: int


CHART_TIMEFRAMES: dict[str, TimeframeRules] = {
    "5Min": {"bar": "5Min", "pad_days": 1, "span_max": 10, "warmup_days": 5},
    "1Hour": {"bar": "1Hour", "pad_days": 7, "span_max": 90, "warmup_days": 46},
    "1Day": {"bar": "1Day", "pad_days": 120, "span_max": 900, "warmup_days": 300},
}
SESSION_SOURCE = "30Min"


def session_hour_bars(bars: list[Bar]) -> list[BarRow]:
    if not bars:
        return []
    frame = _bar_frame(bars)
    regular = regular_session(frame)
    if regular.empty:
        return []
    index = cast(DatetimeIndex, regular.index)
    starts = session_starts(index)
    elapsed = (index - starts) // Timedelta(hours=1)
    folded = (
        cast(Any, regular)
        .groupby(starts + elapsed * Timedelta(hours=1))
        .agg(
            o=("open", "first"),
            h=("high", "max"),
            l=("low", "min"),
            c=("close", "last"),
            v=("volume", "sum"),
        )
    )
    return [
        {
            "t": start.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            "o": float(row.o),
            "h": float(row.h),
            "l": float(row.l),
            "c": float(row.c),
            "v": float(row.v),
        }
        for start, row in folded.iterrows()
    ]


def chart_window(timeframe: str, opened: date, closed: date) -> tuple[datetime, datetime, datetime]:
    rules = CHART_TIMEFRAMES[timeframe]
    pad = timedelta(days=rules["pad_days"])
    display = opened - pad
    end = closed + pad
    if (end - display).days > rules["span_max"]:
        display = end - timedelta(days=rules["span_max"])
    data = display - timedelta(days=rules["warmup_days"])
    return (
        datetime.combine(data, dtime(0, 0), TRADING_ZONE),
        datetime.combine(display, dtime(0, 0), TRADING_ZONE),
        datetime.combine(end, dtime(23, 59), TRADING_ZONE),
    )


def bars_atr(bars: list[Bar]) -> float | None:
    if len(bars) <= settings.indicators.period:
        return None
    return latest_atr(_bar_frame(bars))


def bar_time(bar: Bar) -> datetime:
    return datetime.fromisoformat(bar.at.replace("Z", "+00:00")).astimezone(TRADING_ZONE)


def bar_row(bar: Bar) -> BarRow:
    return {
        "t": bar.at,
        "o": bar.open,
        "h": bar.high,
        "l": bar.low,
        "c": bar.close,
        "v": bar.volume,
    }


def _bar_frame(bars: list[Bar]) -> DataFrame:
    frame = DataFrame(
        {
            "open": [bar.open for bar in bars],
            "high": [bar.high for bar in bars],
            "low": [bar.low for bar in bars],
            "close": [bar.close for bar in bars],
            "volume": [bar.volume for bar in bars],
        },
        index=DatetimeIndex([bar_time(bar) for bar in bars], tz=TRADING_ZONE),
    )
    return frame.sort_index()
