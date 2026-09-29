from datetime import date, datetime, timedelta
from typing import TypedDict

from pandas import DataFrame, DatetimeIndex, Series, Timestamp

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
    means = {length: close.rolling(length).mean() for length in lengths}
    return [
        Average(length=length, values=mean.astype(object).where(mean.notna(), None).tolist())
        for length, mean in means.items()
    ]
