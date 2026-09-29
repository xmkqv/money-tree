from datetime import date, datetime, timedelta
from typing import TypedDict

from pandas import DataFrame, DatetimeIndex, Series, Timestamp

from mt.data.bars import Bar, bar_frame
from mt.exchange import midnight, session_starts
from mt.frames import regular_session
from mt.indicators import sma
from mt.rules.sections import ChartTimeframeSection


class Average(TypedDict):
    length: int
    values: list[float | None]


class Chart(TypedDict):
    name: str | None
    displayFromAt: str
    averages: list[Average]
    bars: list[Bar]


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
    index = DatetimeIndex(regular.index)
    starts = session_starts(index)
    folded = regular.groupby(starts + (index - starts).floor("1h")).agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
    )
    return [
        Bar(t=t, o=o, h=h, l=low, c=c, v=v)
        for t, o, h, low, c, v in zip(
            folded.index,
            folded["open"],
            folded["high"],
            folded["low"],
            folded["close"],
            folded["volume"],
            strict=True,
        )
    ]


def chart_window(
    spans: ChartTimeframeSection, opened_on: date, closed_on: date
) -> tuple[datetime, datetime, datetime]:
    pad = timedelta(days=spans.pad_days)
    end_on = closed_on + pad
    display_on = max(opened_on - pad, end_on - timedelta(days=spans.span_days_max))
    data_on = display_on - timedelta(days=spans.warm_up_days)
    return (
        midnight(data_on),
        midnight(display_on),
        midnight(end_on + timedelta(days=1)) - timedelta(minutes=1),
    )


def bar_averages(bars: list[Bar], lengths: tuple[int, ...]) -> list[Average]:
    close = Series([bar.close for bar in bars], dtype=float)
    return [Average(length=length, values=_nullable(sma(close, length))) for length in lengths]


def _regular(bars: list[Bar]) -> DataFrame:
    if not bars:
        return DataFrame()
    return regular_session(bar_frame(bars))


def _nullable(values: Series) -> list[float | None]:
    return values.astype(object).where(values.notna(), None).tolist()
