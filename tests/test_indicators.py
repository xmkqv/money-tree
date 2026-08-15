from __future__ import annotations

import unittest

import polars as pl

from money_tree.indicators import calculate_indicators


class IndicatorTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
