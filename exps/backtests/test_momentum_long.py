import unittest
from unittest.mock import patch

import polars as pl

from money_tree.strategies.momentum_long import (
    EntryDecision,
    calculate_indicators,
    calculate_trailing_stop_price,
    decide_entry,
    should_flatten,
)


class MomentumIndicatorsTest(unittest.TestCase):
    def test_identifies_strong_uptrend(self) -> None:
        frame = pl.DataFrame({"close": [100.0 + index for index in range(220)]})
        frame = frame.with_columns(
            high=pl.col("close") + 1,
            low=pl.col("close") - 1,
        )

        result = calculate_indicators(frame).row(-1, named=True)

        self.assertGreater(result["sma_50"], result["sma_200"])
        self.assertEqual(result["rsi_14"], 100.0)
        self.assertGreater(result["adx_14"], 25.0)
        self.assertGreater(result["atr_14"], 0.0)


class MomentumRulesTest(unittest.TestCase):
    def setUp(self) -> None:
        size = 210
        self.frame = pl.DataFrame(
            {
                "high": [122.0] * size,
                "low": [80.0 if index == size - 5 else 100.0 for index in range(size)],
                "close": [110.0] * size,
            }
        )
        self.enriched = (
            self.frame.with_row_index()
            .with_columns(
                close=(
                    pl.when(pl.col("index") == size - 2)
                    .then(100.0)
                    .when(pl.col("index") == size - 1)
                    .then(120.0)
                    .otherwise(pl.col("close"))
                ),
                sma_20=pl.when(pl.col("index") == size - 1).then(110.0).otherwise(101.0),
                sma_50=pl.lit(105.0),
                sma_200=pl.lit(100.0),
                rsi_14=pl.lit(60.0),
                adx_14=pl.lit(30.0),
                atr_14=pl.lit(4.0),
            )
            .drop("index")
        )

    def test_returns_entry_when_all_rules_hold(self) -> None:
        with patch(
            "money_tree.strategies.momentum_long._indicator_plan",
            return_value=self.enriched.lazy(),
        ):
            decision = decide_entry(self.frame)

        self.assertEqual(decision, EntryDecision(protective_stop_price=79.99))

    def test_returns_true_when_both_flatten_conditions_hold(self) -> None:
        enriched = (
            self.enriched.with_row_index()
            .with_columns(
                close=pl.when(pl.col("index") == len(self.enriched) - 1)
                .then(99.0)
                .otherwise(pl.col("close")),
                rsi_14=pl.when(pl.col("index") == len(self.enriched) - 1)
                .then(49.0)
                .otherwise(pl.col("rsi_14")),
            )
            .drop("index")
        )
        with patch(
            "money_tree.strategies.momentum_long._indicator_plan",
            return_value=enriched.lazy(),
        ):
            self.assertTrue(should_flatten(self.frame))

    def test_never_lowers_trailing_protective_stop(self) -> None:
        self.assertEqual(calculate_trailing_stop_price(120.0, 4.0, 100.0), 114.0)
        self.assertEqual(calculate_trailing_stop_price(104.0, 4.0, 100.0), 100.0)


if __name__ == "__main__":
    unittest.main()
