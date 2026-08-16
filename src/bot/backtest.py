from datetime import datetime
from importlib import import_module
from typing import Protocol, cast

from bot.config import settings


class StrategyType(Protocol):
    def __call__(
        self,
        *,
        broker: object,
        parameters: dict[str, float],
    ) -> object: ...

    def backtest(
        self,
        data_source: object,
        start: datetime,
        end: datetime,
        *,
        parameters: dict[str, float],
    ) -> object: ...


def load_strategy(name: str) -> StrategyType:
    from lumibot.strategies import Strategy as LumibotStrategy

    module_name = name.replace("-", "_")
    if not module_name.isidentifier():
        raise ValueError(f"invalid strategy name: {name}")
    module = import_module(f"bot.strategies.{module_name}")
    strategy = getattr(module, "Strategy")
    if not isinstance(strategy, type) or not issubclass(strategy, LumibotStrategy):
        raise TypeError(f"bot.strategies.{module_name}.Strategy is not a Lumibot strategy")
    return cast(StrategyType, strategy)


def run(strategy_name: str, start: datetime, end: datetime) -> object:
    backtesting = import_module("lumibot.backtesting")
    data_source = getattr(backtesting, "YahooDataBacktesting")
    strategy = load_strategy(strategy_name)
    return strategy.backtest(
        data_source,
        start,
        end,
        parameters=settings.risk_parameters,
    )
