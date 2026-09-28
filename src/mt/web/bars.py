from datetime import date, datetime, timedelta
from math import isfinite
from typing import TypedDict, cast

from pandas import DataFrame, DatetimeIndex, Series, Timedelta, Timestamp

from mt.data.bars import Bar, bar_frame
from mt.exchange import midnight, session_starts
from mt.frames import regular_session
from mt.indicators import latest_atr
from mt.rules.sections import ChartTimeframeSection
from mt.rules.shared import settings
from mt.rules.values import ChartTimeframe


def _regular(bars: list[Bar]) -> DataFrame:
    if not bars:
        return DataFrame()
    return regular_session(bar_frame(bars))


def session_bars(bars: list[Bar]) -> list[Bar]:
    regular = _regular(bars)
    if regular.empty:
        return []
    timestamps = set(regular.index)
    return [bar for bar in bars if Timestamp(bar.opened_at) in timestamps]


def session_hour_bars(bars: list[Bar]) -> list[Bar]:
    regular = _regular(bars)
    if regular.empty:
        return []
    index = cast(DatetimeIndex, regular.index)
    starts = session_starts(index)
    elapsed = (index - starts) // Timedelta(hours=1)
    folded = regular.groupby(starts + elapsed * Timedelta(hours=1)).agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
    )
    return [
        Bar(
            t=cast(datetime, opened_at),
            o=float(row["open"]),
            h=float(row["high"]),
            l=float(row["low"]),
            c=float(row["close"]),
            v=float(row["volume"]),
        )
        for opened_at, row in folded.iterrows()
    ]


def chart_window(
    spans: ChartTimeframeSection, opened: date, closed: date
) -> tuple[datetime, datetime, datetime]:
    pad = timedelta(days=spans.pad_days)
    display = opened - pad
    end = closed + pad
    if (end - display).days > spans.span_max:
        display = end - timedelta(days=spans.span_max)
    data = display - timedelta(days=spans.warm_up_days)
    return (
        midnight(data),
        midnight(display),
        midnight(end + timedelta(days=1)) - timedelta(minutes=1),
    )


def bars_atr(bars: list[Bar]) -> float | None:
    period = settings.indicators.period
    if len(bars) <= period:
        return None
    return latest_atr(bar_frame(bars), period)


class Chart(TypedDict):
    symbol: str
    name: str
    timeframe: ChartTimeframe
    displayFrom: str
    averages: list[Average]
    bars: list[Bar]


class Average(TypedDict):
    length: int
    values: list[float | None]


def bar_averages(bars: list[Bar], lengths: tuple[int, ...]) -> list[Average]:
    close = Series([bar.close for bar in bars], dtype=float)
    return [
        Average(
            length=length,
            values=[
                float(value) if isfinite(value) else None
                for value in close.rolling(length, min_periods=length).mean()
            ],
        )
        for length in lengths
    ]
