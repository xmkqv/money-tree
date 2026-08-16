from typing import Protocol

from bot.backtest import load_strategy
from bot.broker import build_alpaca_broker
from bot.config import settings


class Trader(Protocol):
    def add_strategy(self, strategy: object) -> None: ...

    def run_all(self) -> object: ...


def build_trader() -> Trader:
    from lumibot.traders import Trader as LumibotTrader

    return LumibotTrader()


def run(strategy_name: str) -> None:
    broker = build_alpaca_broker()
    strategy = load_strategy(strategy_name)(
        broker=broker,
        parameters=settings.risk_parameters,
    )
    trader = build_trader()
    trader.add_strategy(strategy)
    trader.run_all()
