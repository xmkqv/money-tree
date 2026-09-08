from mt.config.values import STRATEGY_KEYS, StrategyKey

from .base import Strategy
from .breakout_5m import Breakout5m
from .breakout_10m import Breakout10m
from .daily_sma import DailySma
from .daily_tfb import DailyTfb


STRATEGIES: tuple[type[Strategy], ...] = (Breakout5m, Breakout10m, DailySma, DailyTfb)
STRATEGIES_BY_KEY: dict[StrategyKey, type[Strategy]] = {cls.key: cls for cls in STRATEGIES}
STRATEGIES_BY_CODE: dict[str, type[Strategy]] = {cls.code: cls for cls in STRATEGIES}

if tuple(cls.key for cls in STRATEGIES) != STRATEGY_KEYS:
    raise ValueError("registered strategies must match StrategyKey in order")
if len(STRATEGIES_BY_CODE) != len(STRATEGIES):
    raise ValueError("strategy order-tag codes must be unique")
for _strategy in STRATEGIES:
    if _strategy.key != f"{_strategy.family}_{_strategy.variation.lower()}":
        raise ValueError(f"{_strategy.__name__} key must be its family and variation")
    if len(_strategy.code) != 1:
        raise ValueError(f"{_strategy.__name__} order-tag code must be one character")


def strategy_class(key: StrategyKey) -> type[Strategy]:
    return STRATEGIES_BY_KEY[key]
