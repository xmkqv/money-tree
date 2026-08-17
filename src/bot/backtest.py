from datetime import datetime
from importlib import import_module
from typing import Any, cast

from bot.config import settings


def load_strategy(name: str):
    from lumibot.strategies import Strategy as LumibotStrategy

    strategy = import_module(f"bot.strategies.{name}").Strategy
    if not isinstance(strategy, type) or not issubclass(strategy, LumibotStrategy):
        raise TypeError(f"bot.strategies.{name}.Strategy is not a Lumibot strategy")
    return strategy


def run(strategy_name: str, start: datetime, end: datetime) -> object:
    from lumibot.backtesting import YahooDataBacktesting

    return cast(Any, load_strategy(strategy_name)).backtest(
        YahooDataBacktesting,
        start,
        end,
        parameters=settings.risk_parameters,
    )
