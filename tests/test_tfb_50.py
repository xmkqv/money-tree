from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta
from unittest.mock import patch

import polars as pl

from money_tree.strategies.tfb_50 import (
    EntryDecision,
    ExitSignal,
    decide_entry,
    decide_exit,
    highest_confirmed_swing_low_since,
    latest_confirmed_swing_low,
)


def replace_row(frame: pl.DataFrame, column: str, index: int, value: float) -> pl.DataFrame:
    row_index = index if index >= 0 else len(frame) + index
    return (
        frame.with_row_index("row_index")
        .with_columns(
            pl.when(pl.col("row_index") == row_index)
            .then(value)
            .otherwise(pl.col(column))
            .alias(column)
        )
        .drop("row_index")
    )


class Tfb50EntryTest(unittest.TestCase):
    def setUp(self) -> None:
        size = 60
        started_at = datetime(2026, 1, 1)
        self.frame = pl.DataFrame(
            {
                "datetime": [started_at + timedelta(days=index) for index in range(size)],
                "high": [110.0] * size,
                "low": [80.0 if index == size - 5 else 100.0 for index in range(size)],
                "close": [120.0 if index == size - 1 else 105.0 for index in range(size)],
            }
        )
        self.enriched = (
            self.frame.with_row_index("row_index")
            .with_columns(
                sma_20=pl.lit(100.0),
                sma_50=(pl.when(pl.col("row_index") == size - 1).then(110.0).otherwise(100.0)),
                sma_200=pl.lit(90.0),
                rsi_14=pl.lit(55.0),
                atr_14=pl.lit(2.0),
                adx_14=pl.lit(19.0),
            )
            .drop("row_index")
        )

    def test_returns_entry_when_all_rules_hold(self) -> None:
        with patch(
            "money_tree.strategies.tfb_50.indicator_plan",
            return_value=self.enriched.lazy(),
        ):
            decision = decide_entry(self.frame)

        self.assertEqual(decision, EntryDecision(protective_stop_price=80.0))

    def test_requires_each_entry_rule(self) -> None:
        cases = {
            "close above SMA": replace_row(self.enriched, "sma_50", -1, 121.0),
            "rising SMA": replace_row(self.enriched, "sma_50", -4, 110.0),
            "low ADX": replace_row(self.enriched, "adx_14", -1, 20.0),
            "close above prior high": replace_row(self.enriched, "high", -2, 120.0),
        }

        for name, enriched in cases.items():
            with (
                self.subTest(name=name),
                patch(
                    "money_tree.strategies.tfb_50.indicator_plan",
                    return_value=enriched.lazy(),
                ),
            ):
                self.assertIsNone(decide_entry(self.frame))


class Tfb50ExitTest(unittest.TestCase):
    def setUp(self) -> None:
        size = 30
        self.frame = pl.DataFrame(
            {
                "high": [110.0] * size,
                "low": [100.0] * size,
                "close": [105.0] * size,
            }
        )
        self.enriched = self.frame.with_columns(
            sma_20=pl.lit(100.0),
            sma_50=pl.lit(100.0),
            sma_200=pl.lit(90.0),
            rsi_14=pl.lit(55.0),
            atr_14=pl.lit(2.0),
            adx_14=pl.lit(19.0),
        )

    def test_returns_previous_low_exit(self) -> None:
        enriched = replace_row(self.enriched, "close", -1, 99.0)
        with patch(
            "money_tree.strategies.tfb_50.indicator_plan",
            return_value=enriched.lazy(),
        ):
            self.assertEqual(decide_exit(self.frame), ExitSignal.PREVIOUS_LOW)

    def test_returns_emergency_exit(self) -> None:
        enriched = replace_row(self.enriched, "low", -2, 80.0)
        enriched = replace_row(enriched, "close", -1, 99.0)
        enriched = replace_row(enriched, "rsi_14", -1, 49.0)
        with patch(
            "money_tree.strategies.tfb_50.indicator_plan",
            return_value=enriched.lazy(),
        ):
            self.assertEqual(decide_exit(self.frame), ExitSignal.EMERGENCY)

    def test_requires_both_emergency_conditions(self) -> None:
        enriched = replace_row(self.enriched, "low", -2, 80.0)
        enriched = replace_row(enriched, "close", -1, 99.0)
        with patch(
            "money_tree.strategies.tfb_50.indicator_plan",
            return_value=enriched.lazy(),
        ):
            self.assertIsNone(decide_exit(self.frame))


class Tfb50SwingLowTest(unittest.TestCase):
    def setUp(self) -> None:
        started_at = datetime(2026, 1, 1)
        lows = [12.0, 11.0, 7.0, 11.0, 12.0, 11.0, 8.0, 11.0, 12.0, 13.0]
        self.frame = pl.DataFrame(
            {
                "datetime": [started_at + timedelta(days=index) for index in range(len(lows))],
                "high": [value + 2 for value in lows],
                "low": lows,
                "close": [value + 1 for value in lows],
            }
        )

    def test_returns_latest_confirmed_swing_low(self) -> None:
        self.assertEqual(latest_confirmed_swing_low(self.frame), 8.0)

    def test_returns_highest_confirmed_swing_low_since_entry(self) -> None:
        self.assertEqual(
            highest_confirmed_swing_low_since(self.frame, date(2026, 1, 5)),
            8.0,
        )

    def test_excludes_swing_low_without_two_later_bars(self) -> None:
        incomplete = replace_row(self.frame, "low", -1, 6.0)

        self.assertEqual(latest_confirmed_swing_low(incomplete), 8.0)


if __name__ == "__main__":
    unittest.main()
