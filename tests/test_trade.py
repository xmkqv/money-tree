import unittest
from unittest.mock import Mock, patch

from bot.config import Settings
from bot.trade import run


class TradeConfigurationTest(unittest.TestCase):
    def test_new_worker_variable_names(self) -> None:
        configuration = Settings(
            _env_file=None,
            STRATEGY="readme",
            ALPACA_API_KEY="paper-key",
            ALPACA_API_SECRET="paper-secret",
            ALPACA_IS_PAPER="true",
            RISK_PER_DAY_MAX="0.02",
            RISK_PER_TRADE_MAX="0.005",
        )

        self.assertEqual(configuration.strategy, "readme")
        self.assertTrue(configuration.alpaca_is_paper)
        self.assertEqual(configuration.risk_per_day_max, 0.02)
        self.assertEqual(configuration.risk_per_trade_max, 0.005)

    @patch("bot.trade.build_trader")
    @patch("bot.trade.load_strategy")
    @patch("bot.trade.build_alpaca_broker")
    def test_readme_strategy_starts_with_mocked_alpaca(
        self,
        build_broker: Mock,
        load_strategy: Mock,
        build_trader: Mock,
    ) -> None:
        broker = build_broker.return_value
        strategy_type = load_strategy.return_value
        strategy = strategy_type.return_value
        trader = build_trader.return_value

        run("readme")

        load_strategy.assert_called_once_with("readme")
        strategy_type.assert_called_once()
        self.assertIs(strategy_type.call_args.kwargs["broker"], broker)
        trader.add_strategy.assert_called_once_with(strategy)
        trader.run_all.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
