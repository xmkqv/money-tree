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


def market_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        moment = value
    elif isinstance(value, str):
        moment = cast(datetime, pd.Timestamp(value).to_pydatetime())
    else:
        raise TypeError(f"unsupported timestamp {value!r}")
    if moment.tzinfo is None:
        return moment.replace(tzinfo=MARKET_TIMEZONE)
    return moment.astimezone(MARKET_TIMEZONE)


def session_rows(
    frame: pd.DataFrame,
    trading_date: date,
    observed_at: datetime,
) -> list[tuple[datetime, float, float, float]]:
    observed_at = market_datetime(observed_at)
    rows: list[tuple[datetime, float, float, float]] = []
    for index, row in frame.iterrows():
        moment = market_datetime(index)
        if moment.date() != trading_date:
            continue
        if moment >= observed_at:
            continue
        if not MARKET_OPEN <= moment.time() < ENTRY_END:
            continue
        rows.append((moment, float(row["high"]), float(row["low"]), float(row["close"])))
    return sorted(rows, key=lambda row: row[0])


def find_opening_range(
    frame: pd.DataFrame,
    trading_date: date,
    observed_at: datetime,
) -> OpeningRange | None:
    rows = [
        row
        for row in session_rows(frame, trading_date, observed_at)
        if MARKET_OPEN <= row[0].time() < RANGE_END
    ]
    if len(rows) < 5:
        return None
    return OpeningRange(
        high=max(row[1] for row in rows),
        low=min(row[2] for row in rows),
    )


def find_breakout(
    frame: pd.DataFrame,
    trading_date: date,
    observed_at: datetime,
) -> Breakout | None:
    opening_range = find_opening_range(frame, trading_date, observed_at)
    if opening_range is None:
        return None
    for moment, _, _, close in session_rows(frame, trading_date, observed_at):
        if moment.time() < RANGE_END:
            continue
        if close > opening_range.high:
            return Breakout(moment, close, BreakoutSide.LONG, opening_range.low)
        if close < opening_range.low:
            return Breakout(moment, close, BreakoutSide.SHORT, opening_range.high)
    return None


def is_latest_breakout(
    frame: pd.DataFrame,
    breakout: Breakout,
    trading_date: date,
    observed_at: datetime,
) -> bool:
    rows = [
        row for row in session_rows(frame, trading_date, observed_at) if row[0].time() >= RANGE_END
    ]
    return bool(rows) and rows[-1][0] == breakout.closed_at


def should_close(moment: datetime) -> bool:
    return market_datetime(moment).time() >= ENTRY_END
