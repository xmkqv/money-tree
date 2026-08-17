from typing import ClassVar

from lumibot.strategies import Strategy as LumibotStrategy

from bot.strategies.shared import RiskParameters


class Strategy(LumibotStrategy):
    parameters: ClassVar[RiskParameters] = {
        "risk_per_day_max": 0.02,
        "risk_per_trade_max": 0.005,
    }

    def initialize(self) -> None:
        self.sleeptime = "1D"

    def on_trading_iteration(self) -> None:
        return
