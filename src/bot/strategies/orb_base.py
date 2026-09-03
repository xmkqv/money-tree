from dataclasses import dataclass
from datetime import date, time
from math import ceil, floor, isfinite
from typing import Any, cast

from pandas import DataFrame, DatetimeIndex, Series, Timestamp

from .shared import (
    TRADING_ZONE,
    Direction,
)


ORB_TURNOVER_USD_MIN = 20_000_000.0

ORB_PRICE_USD_MIN = 5.0

ORB_RANGE_FRACTION_MIN = 0.004
ORB_STOP_FRACTION_MIN = 0.01
ORB_STOP_FRACTION_MAX = 0.05

ORB_RISK_MAX = 0.0015
ORB_POSITIONS_MAX = 3


@dataclass(frozen=True, slots=True)
class OrbSetup:
    direction: Direction
    high: float
    low: float
    close: float
    stop: float

    @property
    def risk(self) -> float:
        return abs(self.close - self.stop)


@dataclass(frozen=True, slots=True)
class SessionVolume:
    ratio: float
    turnover: float


def range_stop(direction: Direction, high: float, low: float) -> float:
    return low + (high - low) * (0.75 if direction == 1 else 0.25)


def range_break(high: float, low: float, close: float) -> Direction | None:
    if not all(isfinite(value) for value in (high, low, close)):
        return None
    return 1 if close > high else -1 if close < low else None


def orb_setup(high: float, low: float, close: float) -> OrbSetup | None:
    direction = range_break(high, low, close)
    if direction is None or close < ORB_PRICE_USD_MIN:
        return None
    if high - low < ORB_RANGE_FRACTION_MIN * close:
        return None
    stop = range_stop(direction, high, low)
    fraction = abs(close - stop) / close
    if not ORB_STOP_FRACTION_MIN <= fraction <= ORB_STOP_FRACTION_MAX:
        return None
    return OrbSetup(direction, high, low, close, stop)


def round_stop(direction: Direction, stop: float) -> float:
    pennies = round(stop * 100.0, 6)
    return (floor(pennies) if direction == 1 else ceil(pennies)) / 100.0


def session_volume(frame: DataFrame, day: date, clock: time) -> SessionVolume | None:
    regular = cast(DataFrame, cast(Any, frame).between_time("09:30", "15:59"))
    index = cast(DatetimeIndex, regular.index)
    pandas_index = cast(Any, index)
    session_dates = cast(DatetimeIndex, pandas_index.normalize())
    current_session = Timestamp(day, tz=TRADING_ZONE)
    is_relevant = (cast(Any, session_dates) == current_session) | (
        cast(Any, session_dates) < current_session
    )
    volume = cast(Series, regular["volume"])
    aggregates = DataFrame(
        {
            "session_date": session_dates,
            "daily_turnover": volume * cast(Series, regular["close"]),
            "cumulative_volume": cast(
                Series,
                cast(Any, volume).where(pandas_index.time <= clock, 0.0),
            ),
        },
        index=index,
    )
    columns = ["daily_turnover", "cumulative_volume"]
    grouped = cast(
        DataFrame,
        cast(Any, aggregates).loc[is_relevant].groupby("session_date", sort=True)[columns].sum(),
    )
    if current_session not in grouped.index:
        return None
    grouped_index = cast(Any, cast(DatetimeIndex, grouped.index))
    history = cast(DataFrame, cast(Any, grouped).loc[grouped_index < current_session].tail(20))
    if len(history) != 20:
        return None
    clock_average = float(cast(Any, history["cumulative_volume"]).mean())
    turnover = float(cast(Any, history["daily_turnover"]).mean())
    current = float(cast(Any, grouped).loc[current_session, "cumulative_volume"])
    if not all(isfinite(value) for value in (clock_average, turnover, current)):
        return None
    if clock_average <= 0:
        return None
    return SessionVolume(current / clock_average, turnover)


def is_relative_volume_ready(
    frame: DataFrame,
    day: date,
    clock: time,
    multiple: float,
) -> bool:
    if frame.empty:
        return False
    volume = session_volume(frame, day, clock)
    if volume is None:
        return False
    return volume.turnover >= ORB_TURNOVER_USD_MIN and volume.ratio >= multiple
