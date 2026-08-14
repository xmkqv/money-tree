from datetime import date, datetime, time, timedelta
from unittest import TestCase
from zoneinfo import ZoneInfo

import polars as pl

from money_tree.model import Direction
from money_tree.opening_range import Breakout, find_breakout

MARKET_TIMEZONE = ZoneInfo("America/New_York")
SESSION_DATE = date(2026, 8, 14)


def bars(close_prices: list[float], *, flat_range: bool = False) -> pl.DataFrame:
    closed_at = datetime.combine(SESSION_DATE, time(9, 30), MARKET_TIMEZONE)
    high_price = 100.0 if flat_range else 101.0
    low_price = 100.0 if flat_range else 99.0
    return pl.DataFrame(
        {
            "datetime": [
                closed_at + timedelta(minutes=index) for index in range(len(close_prices))
            ],
            "high": [high_price] * len(close_prices),
            "low": [low_price] * len(close_prices),
            "close": close_prices,
        }
    )


def observe_after(frame: pl.DataFrame) -> datetime:
    return frame["datetime"][-1] + timedelta(minutes=1)


class FindBreakoutTest(TestCase):
    def test_returns_long_when_latest_bar_is_first_breakout(self) -> None:
        frame = bars([100.0, 100.0, 100.0, 100.0, 100.0, 102.0])

        breakout = find_breakout(frame, SESSION_DATE, observe_after(frame))

        self.assertEqual(
            breakout,
            Breakout(frame["datetime"][-1], 102.0, Direction.LONG, 99.0),
        )

    def test_returns_short_when_latest_bar_is_first_breakout(self) -> None:
        frame = bars([100.0, 100.0, 100.0, 100.0, 100.0, 98.0])

        breakout = find_breakout(frame, SESSION_DATE, observe_after(frame))

        self.assertEqual(
            breakout,
            Breakout(frame["datetime"][-1], 98.0, Direction.SHORT, 101.0),
        )

    def test_returns_none_when_breakout_is_not_latest_bar(self) -> None:
        frame = bars([100.0, 100.0, 100.0, 100.0, 100.0, 102.0, 100.0])

        breakout = find_breakout(frame, SESSION_DATE, observe_after(frame))

        self.assertIsNone(breakout)

    def test_returns_none_when_opening_range_has_fewer_than_five_bars(self) -> None:
        frame = bars([100.0, 100.0, 100.0, 102.0])

        breakout = find_breakout(frame, SESSION_DATE, observe_after(frame))

        self.assertIsNone(breakout)

    def test_rejects_flat_opening_range(self) -> None:
        frame = bars([100.0, 100.0, 100.0, 100.0, 100.0, 101.0], flat_range=True)

        with self.assertRaisesRegex(
            ValueError,
            "opening range high price must exceed its low price",
        ):
            find_breakout(frame, SESSION_DATE, observe_after(frame))
