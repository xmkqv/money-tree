from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from unittest import TestCase

from money_tree.cli import build_parser, default_state_path, run_trade
from money_tree.model import StrategyName, TradingMode


class CommandTest(TestCase):
    def test_parses_backtest_for_each_strategy(self) -> None:
        parser = build_parser()

        opening_range = parser.parse_args(["strategy", "backtest", "opening-range"])
        momentum_long = parser.parse_args(["strategy", "backtest", "momentum-long"])

        self.assertEqual(opening_range.strategy_name, StrategyName.OPENING_RANGE)
        self.assertEqual(momentum_long.strategy_name, StrategyName.MOMENTUM_LONG)

    def test_parses_trade_for_each_strategy_and_mode(self) -> None:
        parser = build_parser()

        for strategy in StrategyName:
            for mode in TradingMode:
                with self.subTest(strategy=strategy, mode=mode):
                    arguments = parser.parse_args(
                        ["strategy", "trade", strategy.value, "--mode", mode.value]
                    )

                    self.assertEqual(arguments.strategy_name, strategy)
                    self.assertEqual(arguments.mode, mode)

    def test_requires_explicit_strategy_selection(self) -> None:
        parser = build_parser()

        with redirect_stderr(StringIO()), self.assertRaises(SystemExit):
            parser.parse_args(["strategy", "backtest"])

    def test_requires_literal_live_confirmation_before_connection(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "requires --confirm live"):
            run_trade(
                StrategyName.MOMENTUM_LONG,
                "SPY",
                TradingMode.LIVE,
                Path("unused.json"),
                confirmation=None,
            )

    def test_rejects_confirmation_in_paper_mode_before_connection(self) -> None:
        with self.assertRaisesRegex(ValueError, "only for live trading"):
            run_trade(
                StrategyName.OPENING_RANGE,
                "SPY",
                TradingMode.PAPER,
                Path("unused.json"),
                confirmation="live",
            )

    def test_returns_strategy_and_mode_specific_state_path(self) -> None:
        self.assertEqual(
            default_state_path(StrategyName.MOMENTUM_LONG, TradingMode.PAPER),
            Path(".money-tree/momentum-long-paper-state.json"),
        )
