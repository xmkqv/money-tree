from bot.strategies.base import StrategyBase


class Strategy(StrategyBase):
    def initialize(self) -> None:
        self.sleeptime = "1D"

    def on_trading_iteration(self) -> None:
        return
