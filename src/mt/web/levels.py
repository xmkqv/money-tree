from datetime import date, datetime, timedelta
from typing import Literal, NotRequired, TypedDict

from mt.data.asset import Asset, AssetType
from mt.data.bars import Bar, BarsClientAlpaca
from mt.exchange import midnight, session_bounds
from mt.rules.sections import DailyAtrSection, DashboardSection
from mt.rules.shared import settings
from mt.rules.values import StrategyKey, Unattributed, is_strategy_key
from mt.sizing import Direction
from mt.strategies.breakout import Breakout, range_level, range_stop
from mt.strategies.daily import Daily
from mt.strategies.registry import STRATEGIES_BY_KEY

from .bars import bars_atr


class OpeningRange(TypedDict):
    high: float
    mid: float
    low: float


class Levels(TypedDict):
    strategy_key: StrategyKey | Unattributed
    range: NotRequired[OpeningRange]
    stop: NotRequired[float]
    targets: NotRequired[list[float]]


async def build_levels(
    bars_client: BarsClientAlpaca,
    dashboard: DashboardSection,
    asset: Asset,
    strategy_key: StrategyKey | Unattributed,
    side: Literal["long", "short"],
    entry: float,
    opened: date,
) -> Levels:
    payload = Levels(strategy_key=strategy_key)
    if asset.asset_type != AssetType.STOCK:
        return payload
    direction: Direction = 1 if side == "long" else -1
    bounds = session_bounds(opened)
    found_class = STRATEGIES_BY_KEY[strategy_key] if is_strategy_key(strategy_key) else None
    if found_class is not None and issubclass(found_class, Breakout) and bounds:
        opens = bounds[0]
        minutes = found_class.rules.opening_minutes
        span = dashboard.levels_range_multiple * minutes
        opening_bars = await bars_client.series(
            asset,
            dashboard.levels_source,
            opens,
            opens + timedelta(minutes=span),
            limit=dashboard.levels_source_bars_max,
            pages_max=1,
        )
        found = _opening_range(opening_bars, opens, minutes)
        if found is not None:
            _add_breakout_levels(payload, found_class, direction, entry, *found)
    elif found_class is not None and issubclass(found_class, Daily):
        historical_bars = await bars_client.series(
            asset,
            "1Day",
            midnight(opened - timedelta(days=dashboard.levels_lookback_days)),
            midnight(opened),
            limit=dashboard.levels_lookback_days,
            pages_max=1,
        )
        average_range = bars_atr(historical_bars)
        if average_range is not None and isinstance(found_class.rules, DailyAtrSection):
            distance = found_class.rules.stop_atr_multiple * average_range
            payload["stop"] = round(entry - direction * distance, 4)
    return payload


def _opening_range(bars: list[Bar], opens: datetime, minutes: int) -> tuple[float, float] | None:
    closes = opens + timedelta(minutes=minutes)
    inside = [bar for bar in bars if opens <= bar.opened_at < closes]
    if not inside:
        return None
    return max(bar.high for bar in inside), min(bar.low for bar in inside)


def _add_breakout_levels(
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
