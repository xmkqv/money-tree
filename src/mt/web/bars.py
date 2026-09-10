from datetime import UTC, date, datetime, timedelta
from datetime import time as dtime
from math import isfinite
from typing import Any, TypedDict, cast

from pandas import DatetimeIndex, Series, Timedelta
from pandas_ta_classic.overlap.sma import sma

from mt.config.sections import ChartTimeframeSection
from mt.config.shared import settings
from mt.data.bars import Bar, bar_frame
from mt.exchange import TRADING_ZONE, session_starts
from mt.frames import regular_session
from mt.indicators import latest_atr


def session_hour_bars(bars: list[Bar]) -> list[Bar]:
    if not bars:
        return []
    frame = bar_frame(bars)
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
    folded.index = folded.index.tz_convert(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return [
        Bar.model_validate(row)
        for row in folded.astype(float).rename_axis("t").reset_index().to_dict("records")
    ]


def chart_window(
    rules: ChartTimeframeSection, opened: date, closed: date
) -> tuple[datetime, datetime, datetime]:
    pad = timedelta(days=rules.pad_days)
    display = opened - pad
    end = closed + pad
    if (end - display).days > rules.span_max:
        display = end - timedelta(days=rules.span_max)
    data = display - timedelta(days=rules.warm_up_days)
    return (
        datetime.combine(data, dtime(0, 0), TRADING_ZONE),
        datetime.combine(display, dtime(0, 0), TRADING_ZONE),
        datetime.combine(end, dtime(23, 59), TRADING_ZONE),
    )


def bars_atr(bars: list[Bar]) -> float | None:
    period = settings.indicators.period
    if len(bars) <= period:
        return None
    return latest_atr(bar_frame(bars), period)


class Average(TypedDict):
    length: int
    values: list[float | None]


def bar_averages(bars: list[Bar], lengths: tuple[int, ...]) -> list[Average]:
    close = Series([bar.close for bar in bars], dtype=float)
    return [
        Average(
            length=length,
            values=[float(value) if isfinite(value) else None for value in values]
            if isinstance(values := sma(close, length=length, talib=False), Series)
            else [None] * len(bars),
        )
        for length in lengths
    ]
