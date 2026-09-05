from dataclasses import dataclass
from datetime import date, time
from math import ceil, floor, isfinite
from typing import Any, cast

from pandas import DataFrame, DatetimeIndex, Series, Timestamp

from bot.types import StrategyName

from .shared import TRADING_ZONE, Direction, regular_session


@dataclass(frozen=True, slots=True)
class SessionVolume:
    ratio: float
    turnover: float


ORB_TURNOVER_USD_MIN = 20_000_000.0
ORB_PRICE_USD_MIN = 5.0
ORB_RANGE_FRACTION_MIN = 0.004
ORB_STOP_FRACTION_MIN = 0.01
ORB_STOP_FRACTION_MAX = 0.05
ORB_RISK_MAX = 0.0015
ORB_POSITIONS_MAX = 3
ORB_HISTORY_SESSIONS = 20
ORB_SIGNAL_CANDLES_MAX = 2
ORB_TRAIL_ATR_MULTIPLE = 1.5
ORB_TRAIL_BARS_MIN = 15
ORB_SCAN_MINUTES = 60
ORB_CLOSE_LEAD_MINUTES = 6
# One row per breakout strategy. The opening-range length is what separates
# them; every other column is read from these tables rather than from a test
# against the name, so another length is a row here and nothing else.
ORB_OPENING_MINUTES: dict[StrategyName, int] = {"orb": 5, "orb_momentum": 10, "orb15": 15}
ORB_STRATEGIES: frozenset[StrategyName] = frozenset(ORB_OPENING_MINUTES)
ORB_VOLUME_MULTIPLES: dict[StrategyName, float] = {
    "orb": 1.3,
    "orb_momentum": 1.5,
    "orb15": 1.3,
}
ORB_TARGET_MULTIPLES: dict[StrategyName, tuple[float, float, float]] = {
    "orb": (1.5, 2.5, 4.0),
    "orb_momentum": (2.0, 3.0, 5.0),
    "orb15": (1.5, 2.5, 4.0),
}
ORB_ENTRY_EXTENSION_MAX: dict[StrategyName, float | None] = {
    "orb": None,
    "orb_momentum": 0.25,
    "orb15": None,
}
# A strategy named here is sized by its own ceiling. One left out — ORB10 — is
# sized by the configured per-trade limit instead.
ORB_RISK_MAXES: dict[StrategyName, float] = {"orb": ORB_RISK_MAX, "orb15": ORB_RISK_MAX}


def range_stop(direction: Direction, high: float, low: float) -> float:
    return low + (high - low) * (0.75 if direction == 1 else 0.25)


def range_break(high: float, low: float, close: float) -> Direction | None:
    if not all(isfinite(value) for value in (high, low, close)):
        return None
    return 1 if close > high else -1 if close < low else None


def is_orb_setup_ready(high: float, low: float, close: float) -> bool:
    direction = range_break(high, low, close)
    if direction is None or close < ORB_PRICE_USD_MIN:
        return False
    if high - low < ORB_RANGE_FRACTION_MIN * close:
        return False
    fraction = abs(close - range_stop(direction, high, low)) / close
    return ORB_STOP_FRACTION_MIN <= fraction <= ORB_STOP_FRACTION_MAX


def round_stop(direction: Direction, stop: float) -> float:
    pennies = round(stop * 100.0, 6)
    return (floor(pennies) if direction == 1 else ceil(pennies)) / 100.0


def session_volume(frame: DataFrame, day: date, clock: time) -> SessionVolume | None:
    regular = regular_session(frame)
    index = cast(DatetimeIndex, regular.index)
    pandas_index = cast(Any, index)
    session_dates = cast(DatetimeIndex, pandas_index.normalize())
    current_session = Timestamp(day, tz=TRADING_ZONE)
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
    relevant = cast(Any, session_dates) <= current_session
    grouped = cast(
        DataFrame,
        cast(Any, aggregates).loc[relevant].groupby("session_date", sort=True)[columns].sum(),
    )
    if current_session not in grouped.index:
        return None
    grouped_index = cast(Any, cast(DatetimeIndex, grouped.index))
    history = cast(
        DataFrame,
        cast(Any, grouped).loc[grouped_index < current_session].tail(ORB_HISTORY_SESSIONS),
    )
    if len(history) != ORB_HISTORY_SESSIONS:
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
