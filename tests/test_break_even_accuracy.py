from unittest import TestCase

import numpy as np

from exps.break_even_accuracy import (
    BreakEvenAccuracySample,
    calculate_break_even_accuracy,
    calculate_break_even_accuracy_evidence,
    sum_by_session,
)


class SumBySessionTest(TestCase):
    def test_sums_values_for_each_session(self) -> None:
        result = sum_by_session(
            np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float64),
            np.array([2, 0, 2], dtype=np.int64),
        )

        np.testing.assert_array_equal(result, np.array([3.0, 0.0, 7.0]))

    def test_rejects_counts_that_do_not_match_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "session counts must match the value count"):
            sum_by_session(
                np.array([1.0, 2.0], dtype=np.float64),
                np.array([1], dtype=np.int64),
            )


class CalculateBreakEvenAccuracyTest(TestCase):
    def test_adds_half_the_cost_to_move_ratio(self) -> None:
        result = calculate_break_even_accuracy(
            np.array([40.0, 60.0], dtype=np.float64),
            np.array([4.0, 6.0], dtype=np.float64),
        )

        self.assertAlmostEqual(float(result[0]), 0.55)

    def test_rejects_sample_without_price_moves(self) -> None:
        with self.assertRaisesRegex(
            RuntimeError,
            "break-even accuracy requires positive price moves",
        ):
            calculate_break_even_accuracy(
                np.zeros(2, dtype=np.float64),
                np.ones(2, dtype=np.float64),
            )


class CalculateBreakEvenAccuracyEvidenceTest(TestCase):
    def test_calculates_an_upper_bound(self) -> None:
        generator = np.random.default_rng(20_260_815)
        sample = BreakEvenAccuracySample(
            generator.lognormal(mean=0.0, sigma=0.3, size=60),
            generator.normal(loc=0.1, scale=0.02, size=60),
            60,
        )

        evidence = calculate_break_even_accuracy_evidence(sample)

        self.assertGreater(evidence.upper_break_even_accuracy, evidence.break_even_accuracy)
        self.assertGreaterEqual(evidence.stationary_block_size, 1)
