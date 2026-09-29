from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal, NotRequired, TypedDict

from mt.data.asset import Asset
from mt.data.bars import Bar, BarsClientAlpaca, bar_frame
from mt.exchange import midnight, session_bounds
from mt.indicators import latest_atr
from mt.rules.sections import Daily20SmaSection, DailyAtrSection, DashboardSection
from mt.rules.settings import RuleSettings
from mt.rules.values import StrategyKey, Unattributed
from mt.sizing import Direction
from mt.strategies.breakout import Breakout, range_level
from mt.strategies.daily import Daily
from mt.strategies.registry import STRATEGIES_BY_KEY

from .strategies import describe_strategy


class OpeningRange(TypedDict):
    high: float
    mid: float
    low: float


class Levels(TypedDict):
    strategy_key: StrategyKey | Unattributed
    range: NotRequired[OpeningRange]
    stop: NotRequired[float]
    targets: NotRequired[list[float]]


@dataclass(frozen=True, slots=True)
class _LevelsRequest:
    asset: Asset
    strategy_key: StrategyKey
    direction: Direction
    entry: float
    opened_on: date


async def build_levels(
    bars_client: BarsClientAlpaca,
    dashboard: DashboardSection,
    rules: RuleSettings,
    asset: Asset,
    strategy_key: StrategyKey,
    side: Literal["long", "short"],
    entry: float,
    opened_on: date,
) -> Levels:
    direction: Direction = 1 if side == "long" else -1
    request = _LevelsRequest(asset, strategy_key, direction, entry, opened_on)
    strategy = STRATEGIES_BY_KEY[strategy_key]
    if issubclass(strategy, Breakout):
        return await _breakout_levels(bars_client, dashboard, rules, strategy, request)
    if strategy_key == "daily_20sma":
        return _daily_20sma_levels(rules.daily_20sma, request)
    if issubclass(strategy, Daily):
        return await _daily_levels(bars_client, dashboard, rules, request)
    return Levels(strategy_key=strategy_key)


async def _breakout_levels(
    bars_client: BarsClientAlpaca,
    dashboard: DashboardSection,
    rules: RuleSettings,
    strategy: type[Breakout],
    request: _LevelsRequest,
) -> Levels:
    empty = Levels(strategy_key=request.strategy_key)
    bounds = session_bounds(request.opened_on)
    if bounds is None:
        return empty
    opens_at, _ = bounds
    described = describe_strategy(strategy, rules)
    opening_minutes = described.rules.opening_minutes
    opening_bars = await bars_client.series(
        request.asset,
        dashboard.levels_source,
        opens_at,
        opens_at + timedelta(minutes=opening_minutes),
        limit=dashboard.levels_source_bars_max,
        pages_max=dashboard.pages_max,
    )
    opening = _try_opening_range(opening_bars, opens_at, opening_minutes)
    if opening is None:
        return empty
    high, low = opening
    family = rules.breakout
    stop = range_level(
        high,
        low,
        family.long_stop_fraction if request.direction == 1 else family.short_stop_fraction,
    )
    return Levels(
        strategy_key=request.strategy_key,
        range=OpeningRange(
            high=round(high, 4),
            mid=round(range_level(high, low, family.mid_fraction), 4),
            low=round(low, 4),
        ),
        stop=round(stop, 4),
        targets=[
            round(value, 4)
            for value in described.target_prices(request.entry, stop, request.direction)
        ],
    )


async def _daily_levels(
    bars_client: BarsClientAlpaca,
    dashboard: DashboardSection,
    rules: RuleSettings,
    request: _LevelsRequest,
) -> Levels:
    empty = Levels(strategy_key=request.strategy_key)
    section = getattr(rules, request.strategy_key)
    if not isinstance(section, DailyAtrSection):
        return empty
    historical_bars = await bars_client.series(
        request.asset,
        "1Day",
        midnight(request.opened_on - timedelta(days=dashboard.levels_lookback_days)),
        midnight(request.opened_on),
        limit=dashboard.levels_lookback_days,
        pages_max=dashboard.pages_max,
    )
    average_range = _try_bars_atr(historical_bars, rules.indicators.period_bars)
    if average_range is None:
        return empty
    distance = section.stop_atr_multiple * average_range
    return Levels(
        strategy_key=request.strategy_key,
        stop=round(request.entry - request.direction * distance, 4),
    )


def _daily_20sma_levels(section: Daily20SmaSection, request: _LevelsRequest) -> Levels:
    return Levels(
        strategy_key=request.strategy_key,
        stop=round(request.entry * (1 - section.stop_fraction), 4),
        targets=[round(request.entry * (1 + gain), 4) for gain in section.target_gains],
    )


def _try_opening_range(
    bars: list[Bar], opens_at: datetime, minutes: int
) -> tuple[float, float] | None:
    closes_at = opens_at + timedelta(minutes=minutes)
    inside = [bar for bar in bars if opens_at <= bar.opened_at < closes_at]
    if not inside:
        return None
    return max(bar.high for bar in inside), min(bar.low for bar in inside)


def _try_bars_atr(bars: list[Bar], period_bars: int) -> float | None:
    if len(bars) <= period_bars:
        return None
    return latest_atr(bar_frame(bars), period_bars)
