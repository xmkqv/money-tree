from __future__ import annotations

import unittest
from unittest.mock import patch

from money_tree.cli import INSTRUMENT_DEFAULT, LIVE_CONFIRMATION, default_state_path
from money_tree.model import StrategyName, TradingMode
from money_tree.worker import WorkerConfig, load_worker_config, run_worker


class LoadWorkerConfigTest(unittest.TestCase):
    def test_loads_paper_mode_when_mode_variable_is_absent(self) -> None:
        config = load_worker_config({"MONEY_TREE_STRATEGY": "opening-range"})

        self.assertEqual(
            config,
            WorkerConfig(StrategyName.OPENING_RANGE, TradingMode.PAPER),
        )

    def test_loads_live_mode(self) -> None:
        config = load_worker_config(
            {
                "MONEY_TREE_STRATEGY": "momentum-long",
                "MONEY_TREE_MODE": "live",
            }
        )

        self.assertEqual(
            config,
            WorkerConfig(StrategyName.MOMENTUM_LONG, TradingMode.LIVE),
        )

    def test_loads_tfb_50_strategy(self) -> None:
        config = load_worker_config(
            {
                "MONEY_TREE_STRATEGY": "tfb-50",
                "MONEY_TREE_MODE": "paper",
            }
        )

        self.assertEqual(
            config,
            WorkerConfig(StrategyName.TFB_50, TradingMode.PAPER),
        )

    def test_rejects_missing_strategy(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "missing MONEY_TREE_STRATEGY"):
            load_worker_config({})

    def test_rejects_unknown_strategy(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "MONEY_TREE_STRATEGY must be one of"):
            load_worker_config({"MONEY_TREE_STRATEGY": "unknown"})

    def test_rejects_unknown_mode(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "MONEY_TREE_MODE must be one of: paper, live"):
            load_worker_config(
                {
                    "MONEY_TREE_STRATEGY": "opening-range",
                    "MONEY_TREE_MODE": "unknown",
                }
            )


class RunWorkerTest(unittest.TestCase):
    @patch("money_tree.worker.run_trade")
    def test_runs_paper_worker_without_confirmation(self, run_trade_mock) -> None:
        config = WorkerConfig(StrategyName.OPENING_RANGE, TradingMode.PAPER)

        run_worker(config)

        run_trade_mock.assert_called_once_with(
            StrategyName.OPENING_RANGE,
            INSTRUMENT_DEFAULT,
            TradingMode.PAPER,
            default_state_path(StrategyName.OPENING_RANGE, TradingMode.PAPER),
            confirmation=None,
        )

    @patch("money_tree.worker.run_trade")
    def test_runs_live_worker_with_confirmation(self, run_trade_mock) -> None:
        config = WorkerConfig(StrategyName.MOMENTUM_LONG, TradingMode.LIVE)

        run_worker(config)

        run_trade_mock.assert_called_once_with(
            StrategyName.MOMENTUM_LONG,
            INSTRUMENT_DEFAULT,
            TradingMode.LIVE,
            default_state_path(StrategyName.MOMENTUM_LONG, TradingMode.LIVE),
            confirmation=LIVE_CONFIRMATION,
        )


if __name__ == "__main__":
    unittest.main()
