from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from enum import StrEnum
from typing import cast
from zoneinfo import ZoneInfo

import pandas as pd

MARKET_TIMEZONE = ZoneInfo("America/New_York")
MARKET_OPEN = time(9, 30)
RANGE_END = time(9, 35)
ENTRY_END = time(15, 55)


class BreakoutSide(StrEnum):
    LONG = "long"
    SHORT = "short"


@dataclass(frozen=True, slots=True)
class OpeningRange:
    high: float
    low: float

    def __post_init__(self) -> None:
        if self.high <= self.low:
            raise ValueError("opening range high must exceed its low")


@dataclass(frozen=True, slots=True)
class Breakout:
    closed_at: datetime
    close: float
    side: BreakoutSide
    stop: float


@dataclass(frozen=True, slots=True)
class _SessionBar:
    closed_at: datetime
    high: float
    low: float
    close: float


def to_market_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        moment = value
    elif isinstance(value, str):
        moment = cast(datetime, pd.Timestamp(value).to_pydatetime())
    else:
        raise TypeError(f"unsupported timestamp {value!r}")
    if moment.tzinfo is None:
        return moment.replace(tzinfo=MARKET_TIMEZONE)
    return moment.astimezone(MARKET_TIMEZONE)


def _session_bars(
    frame: pd.DataFrame,
    trading_date: date,
    observed_at: datetime,
) -> list[_SessionBar]:
    observed_at = to_market_datetime(observed_at)
    bars: list[_SessionBar] = []
    for index, high, low, close in frame[["high", "low", "close"]].itertuples(
        index=True,
        name=None,
    ):
        moment = to_market_datetime(index)
        if moment.date() != trading_date:
            continue
        if moment >= observed_at:
            continue
        if not MARKET_OPEN <= moment.time() < ENTRY_END:
            continue
        bars.append(_SessionBar(moment, float(high), float(low), float(close)))
    return sorted(bars, key=lambda bar: bar.closed_at)


def find_actionable_breakout(
    frame: pd.DataFrame,
    trading_date: date,
    observed_at: datetime,
) -> Breakout | None:
    bars = _session_bars(frame, trading_date, observed_at)
    range_bars = [bar for bar in bars if bar.closed_at.time() < RANGE_END]
    if len(range_bars) < 5:
        return None
    opening_range = OpeningRange(
        high=max(bar.high for bar in range_bars),
        low=min(bar.low for bar in range_bars),
    )
    breakout: Breakout | None = None
    for bar in bars[len(range_bars) :]:
        if breakout is not None:
            return None
        if bar.close > opening_range.high:
            breakout = Breakout(
                bar.closed_at,
                bar.close,
                BreakoutSide.LONG,
                opening_range.low,
            )
        elif bar.close < opening_range.low:
            breakout = Breakout(
                bar.closed_at,
                bar.close,
                BreakoutSide.SHORT,
                opening_range.high,
            )
    return breakout


def should_close(moment: datetime) -> bool:
    return to_market_datetime(moment).time() >= ENTRY_END
