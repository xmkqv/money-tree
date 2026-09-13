from uuid import uuid4

from mt.rules.values import STRATEGY_KEYS, StrategyKey

from .base import Strategy
from .breakout import Breakout5m, Breakout10m
from .daily_sma import DailySma
from .daily_tfb import DailyTfb


ORDER_PREFIX = "mt"

STRATEGIES: tuple[type[Strategy], ...] = (Breakout5m, Breakout10m, DailySma, DailyTfb)
STRATEGIES_BY_KEY: dict[StrategyKey, type[Strategy]] = {cls.key: cls for cls in STRATEGIES}
STRATEGIES_BY_CODE: dict[str, type[Strategy]] = {cls.code: cls for cls in STRATEGIES}

if tuple(cls.key for cls in STRATEGIES) != STRATEGY_KEYS:
    raise ValueError("registered strategies must match STRATEGY_KEYS in order")
if len(STRATEGIES_BY_CODE) != len(STRATEGIES):
    raise ValueError("strategy order codes must be unique")
for _strategy in STRATEGIES:
    if len(_strategy.code) != 1:
        raise ValueError(f"{_strategy.__name__} order code must be one character")


def order_code(strategy_key: StrategyKey) -> str:
    return "-".join((ORDER_PREFIX, STRATEGIES_BY_KEY[strategy_key].code, uuid4().hex[:8]))


def find_order_strategy_key(value: str) -> StrategyKey | None:
    parts = value.split("-")
    if len(parts) < 3 or parts[0] != ORDER_PREFIX:
        return None
    found = STRATEGIES_BY_CODE.get(parts[1])
    return None if found is None else found.key
