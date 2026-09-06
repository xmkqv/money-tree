from dataclasses import dataclass
from typing import Literal
from uuid import uuid4

from mt.strategies.keys import StrategyName
from mt.strategies.registry import STRATEGIES, STRATEGIES_BY_CODE


type OrderKind = Literal["e", "s", "x"]


@dataclass(frozen=True, slots=True)
class OrderTag:
    strategy: StrategyName
    kind: OrderKind
    signal: str
    risk_fraction: float


ORDER_TAG_PREFIX = "mt"
ORDER_TAG_PARTS = 6
RISK_FRACTION_SCALE = 1_000_000
ORDER_KINDS: frozenset[OrderKind] = frozenset({"e", "s", "x"})
STRATEGY_CODES: dict[StrategyName, str] = {cls.key: cls.code for cls in STRATEGIES}


def order_tag(strategy: StrategyName, kind: OrderKind, signal: str, risk_fraction: float) -> str:
    scaled = round(risk_fraction * RISK_FRACTION_SCALE)
    return "-".join(
        (ORDER_TAG_PREFIX, STRATEGY_CODES[strategy], kind, signal, str(scaled), uuid4().hex[:8])
    )


def find_order_tag(value: str) -> OrderTag | None:
    parts = value.split("-")
    if len(parts) != ORDER_TAG_PARTS or parts[0] != ORDER_TAG_PREFIX:
        return None
    found = STRATEGIES_BY_CODE.get(parts[1])
    strategy = None if found is None else found.key
    kind = parts[2]
    if strategy is None or kind not in ORDER_KINDS or not parts[4].isdigit():
        return None
    return OrderTag(strategy, kind, parts[3], int(parts[4]) / RISK_FRACTION_SCALE)
