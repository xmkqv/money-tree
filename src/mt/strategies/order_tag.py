from dataclasses import dataclass
from typing import Literal, get_args
from uuid import uuid4

from mt.config.settings import settings
from mt.config.values import StrategyKey

from .registry import STRATEGIES_BY_CODE, strategy_class


type OrderKind = Literal["e", "s", "x"]
type Unattributed = Literal["unattributed"]


@dataclass(frozen=True, slots=True)
class OrderTag:
    strategy_key: StrategyKey
    kind: OrderKind
    symbol: str
    stop_fraction: float


ORDER_TAG_PREFIX = "mt"
ORDER_TAG_PARTS = 6
ORDER_KINDS: tuple[OrderKind, ...] = get_args(OrderKind.__value__)
UNATTRIBUTED: Unattributed = "unattributed"


def order_tag(strategy_key: StrategyKey, kind: OrderKind, symbol: str, stop_fraction: float) -> str:
    scaled = round(stop_fraction * settings.order_tag.stop_fraction_scale)
    code = strategy_class(strategy_key).code
    return "-".join((ORDER_TAG_PREFIX, code, kind, symbol, str(scaled), uuid4().hex[:8]))


def find_order_tag(value: str) -> OrderTag | None:
    parts = value.split("-")
    if len(parts) != ORDER_TAG_PARTS or parts[0] != ORDER_TAG_PREFIX:
        return None
    found = STRATEGIES_BY_CODE.get(parts[1])
    strategy_key = None if found is None else found.key
    kind = parts[2]
    if strategy_key is None or kind not in ORDER_KINDS or not parts[4].isdigit():
        return None
    return OrderTag(
        strategy_key, kind, parts[3], int(parts[4]) / settings.order_tag.stop_fraction_scale
    )
