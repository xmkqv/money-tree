from dataclasses import dataclass
from typing import Literal, get_args
from uuid import uuid4

from mt.config.values import StrategyKey

from .registry import STRATEGIES_BY_CODE, strategy_class


type OrderKind = Literal["e", "s", "x"]
type Unattributed = Literal["unattributed"]


@dataclass(frozen=True, slots=True)
class OrderTag:
    strategy: StrategyKey
    kind: OrderKind
    signal: str
    risk_fraction: float


ORDER_TAG_PREFIX = "mt"
ORDER_TAG_PARTS = 6
RISK_FRACTION_SCALE = 1_000_000
ORDER_KINDS: tuple[OrderKind, ...] = get_args(OrderKind.__value__)
UNATTRIBUTED: Unattributed = "unattributed"


def order_tag(strategy: StrategyKey, kind: OrderKind, signal: str, risk_fraction: float) -> str:
    scaled = round(risk_fraction * RISK_FRACTION_SCALE)
    code = strategy_class(strategy).code
    return "-".join((ORDER_TAG_PREFIX, code, kind, signal, str(scaled), uuid4().hex[:8]))


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
