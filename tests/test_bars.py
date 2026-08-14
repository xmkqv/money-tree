from datetime import UTC, datetime
from unittest import TestCase

import polars as pl

from money_tree.bars import market_datetime_expression, normalize_price_bars


class NormalizePriceBarsTest(TestCase):
    def test_casts_prices_and_normalizes_nan(self) -> None:
        frame = pl.DataFrame(
            {
                "high": [2],
                "low": [1],
                "close": [float("nan")],
            }
        )

        result = normalize_price_bars(frame)

        self.assertEqual(result.schema["high"], pl.Float64)
        self.assertEqual(result.schema["low"], pl.Float64)
        self.assertEqual(result.schema["close"], pl.Float64)
        self.assertIsNone(result["close"].item())

    def test_rejects_missing_price_columns(self) -> None:
        frame = pl.DataFrame({"high": [2], "low": [1]})

        with self.assertRaisesRegex(ValueError, "missing columns: close"):
            normalize_price_bars(frame)

    def test_rejects_a_high_below_its_low(self) -> None:
        frame = pl.DataFrame({"high": [1], "low": [2], "close": [1.5]})

        with self.assertRaisesRegex(ValueError, "high below its low"):
            normalize_price_bars(frame)


class MarketDatetimeExpressionTest(TestCase):
    def test_localizes_a_naive_timestamp(self) -> None:
        frame = pl.DataFrame({"datetime": [datetime(2026, 8, 14, 9, 30)]})

        result = frame.select(market_datetime_expression(frame)).item()

        self.assertEqual(result.hour, 9)
        self.assertEqual(result.utcoffset().total_seconds(), -4 * 60 * 60)

    def test_converts_an_aware_timestamp(self) -> None:
        frame = pl.DataFrame({"datetime": [datetime(2026, 8, 14, 13, 30, tzinfo=UTC)]})

        result = frame.select(market_datetime_expression(frame)).item()

        self.assertEqual(result.hour, 9)
        self.assertEqual(result.utcoffset().total_seconds(), -4 * 60 * 60)

    def test_rejects_a_non_datetime_column(self) -> None:
        frame = pl.DataFrame({"datetime": ["2026-08-14T09:30:00"]})

        with self.assertRaisesRegex(TypeError, "must use a datetime type"):
            market_datetime_expression(frame)
