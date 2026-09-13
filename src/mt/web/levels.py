from datetime import datetime, timedelta
from typing import NotRequired, TypedDict

from mt.data.bars import Bar
from mt.exchange import trading_time
from mt.rules.shared import settings
from mt.rules.values import StrategyKey, Unattributed
from mt.sizing import Direction
from mt.strategies.breakout import Breakout, range_level, range_stop


class OpeningRange(TypedDict):
    high: float
    mid: float
    low: float


class Levels(TypedDict):
    strategy_key: StrategyKey | Unattributed
    range: NotRequired[OpeningRange]
    stop: NotRequired[float]
    targets: NotRequired[list[float]]
    atr: NotRequired[float]


def opening_range(bars: list[Bar], opens: datetime, minutes: int) -> tuple[float, float] | None:
    closes = opens + timedelta(minutes=minutes)
    inside = [bar for bar in bars if opens <= trading_time(bar.opened_at) < closes]
    if not inside:
        return None
    return max(bar.high for bar in inside), min(bar.low for bar in inside)


def add_breakout_levels(
    payload: Levels,
    strategy: type[Breakout],
    direction: Direction,
    entry: float,
    high: float,
    low: float,
) -> None:
    stop = range_stop(direction, high, low)
    targets = strategy.target_prices(entry, stop, direction)
    payload["range"] = OpeningRange(
        high=round(high, 4),
        mid=round(range_level(high, low, settings.breakout.mid_fraction), 4),
        low=round(low, 4),
    )
    payload["stop"] = round(stop, 4)
    payload["targets"] = [round(value, 4) for value in targets]
