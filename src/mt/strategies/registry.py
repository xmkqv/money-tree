from uuid import uuid4

from mt.rules.values import (
    LIQUIDATE_CODE,
    ORDER_PREFIX,
    STRATEGY_KEYS,
    OrderReason,
    StrategyKey,
    is_order_reason,
)

from .base import Strategy
from .breakout import Breakout5m, Breakout10m, Breakout15m
from .daily_20sma import Daily20Sma
from .daily_sma import DailySma
from .daily_tfb import DailyTfb


CODE_SUFFIX_LENGTH = 16

STRATEGIES: tuple[type[Strategy], ...] = (
    Breakout5m,
    Breakout10m,
    Breakout15m,
    DailySma,
    DailyTfb,
    Daily20Sma,
)
STRATEGIES_BY_KEY: dict[StrategyKey, type[Strategy]] = {cls.key: cls for cls in STRATEGIES}
STRATEGIES_BY_CODE: dict[str, type[Strategy]] = {cls.code: cls for cls in STRATEGIES}

if tuple(cls.key for cls in STRATEGIES) != STRATEGY_KEYS:
    raise ValueError("registered strategies must match STRATEGY_KEYS in order")
if len(STRATEGIES_BY_CODE) != len(STRATEGIES):
    raise ValueError("strategy order codes must be unique")
for _strategy in STRATEGIES:
    if len(_strategy.code) != 1:
        raise ValueError(f"{_strategy.__name__} order code must be one character")


def order_code(code: str, reason: OrderReason) -> str:
    return _code(code, reason)


def liquidate_code() -> str:
    return _code(LIQUIDATE_CODE)


def find_order_strategy_key(value: str) -> StrategyKey | None:
    parts = _order_parts(value)
    if parts is None:
        return None
    found = STRATEGIES_BY_CODE.get(parts[1])
    return None if found is None else found.key


def find_order_reason(value: str) -> OrderReason | None:
    parts = _order_parts(value)
    if parts is None:
        return None
    if parts[1] == LIQUIDATE_CODE:
        return "limit"
    if len(parts) == 4 and is_order_reason(parts[2]):
        return parts[2]
    return None


def _code(*parts: str) -> str:
    return "-".join((ORDER_PREFIX, *parts, uuid4().hex[:CODE_SUFFIX_LENGTH]))


def _order_parts(value: str) -> list[str] | None:
    parts = value.split("-")
    return parts if len(parts) >= 3 and parts[0] == ORDER_PREFIX else None
