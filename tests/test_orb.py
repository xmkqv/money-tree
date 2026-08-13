from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

from money_tree.orb import (
    BreakoutSide,
    find_breakout,
    find_opening_range,
    is_latest_breakout,
    should_close,
)

MARKET_TIMEZONE = ZoneInfo("America/New_York")
TRADING_DATE = date(2026, 8, 13)


def frame(closes: list[float]) -> pd.DataFrame:
    start = datetime(2026, 8, 13, 9, 30, tzinfo=MARKET_TIMEZONE)
    index = [start + timedelta(minutes=offset) for offset in range(len(closes))]
    return pd.DataFrame(
        {
            "high": [max(close, 10.5) for close in closes],
            "low": [min(close, 9.5) for close in closes],
            "close": closes,
        },
        index=index,
    )


def after_last_bar(bars: pd.DataFrame) -> datetime:
    return bars.index[-1].to_pydatetime() + timedelta(minutes=1)


def test_builds_range_from_first_five_minutes() -> None:
    bars = frame([10.0, 10.1, 10.2, 10.3, 10.4])
    opening_range = find_opening_range(bars, TRADING_DATE, after_last_bar(bars))

    assert opening_range is not None
    assert opening_range.high == 10.5
    assert opening_range.low == 9.5


def test_returns_none_when_opening_range_is_incomplete() -> None:
    bars = frame([10.0, 10.1, 10.2, 10.3])
    assert find_opening_range(bars, TRADING_DATE, after_last_bar(bars)) is None


def test_finds_first_close_above_range() -> None:
    bars = frame([10.0, 10.1, 10.2, 10.3, 10.4, 10.2, 10.6])

    breakout = find_breakout(bars, TRADING_DATE, after_last_bar(bars))

    assert breakout is not None
    assert breakout.side is BreakoutSide.LONG
    assert breakout.stop == 9.5
    assert is_latest_breakout(bars, breakout, TRADING_DATE, after_last_bar(bars))


def test_rejects_stale_breakout() -> None:
    bars = frame([10.0, 10.1, 10.2, 10.3, 10.4, 10.6, 10.7])

    breakout = find_breakout(bars, TRADING_DATE, after_last_bar(bars))

    assert breakout is not None
    assert not is_latest_breakout(bars, breakout, TRADING_DATE, after_last_bar(bars))


def test_finds_close_below_range() -> None:
    bars = frame([10.0, 10.1, 10.2, 10.3, 10.4, 9.4])
    breakout = find_breakout(bars, TRADING_DATE, after_last_bar(bars))

    assert breakout is not None
    assert breakout.side is BreakoutSide.SHORT
    assert breakout.stop == 10.5


def test_ignores_bars_not_completed_at_observation_time() -> None:
    bars = frame([10.0, 10.1, 10.2, 10.3, 10.4, 10.6])
    observed_at = datetime(2026, 8, 13, 9, 31, tzinfo=MARKET_TIMEZONE)

    assert find_breakout(bars, TRADING_DATE, observed_at) is None


def test_closes_at_1555_eastern() -> None:
    assert should_close(datetime(2026, 8, 13, 15, 55, tzinfo=MARKET_TIMEZONE))
    assert not should_close(datetime(2026, 8, 13, 15, 54, tzinfo=MARKET_TIMEZONE))
