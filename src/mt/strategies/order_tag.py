from dataclasses import dataclass
from typing import Literal, get_args
from uuid import uuid4

from mt.config.shared import settings
from mt.config.values import StrategyKey

from .registry import STRATEGIES_BY_CODE, strategy_class


type OrderKind = Literal["e", "s", "x"]
type Unattributed = Literal["unattributed"]


@dataclass(frozen=True, slots=True)
class OrderTag:
    strategy_key: StrategyKey
    stop_fraction: float


ORDER_TAG_PREFIX = "mt"
ORDER_KINDS: tuple[OrderKind, ...] = get_args(OrderKind.__value__)
UNATTRIBUTED: Unattributed = "unattributed"


def order_tag(strategy_key: StrategyKey, stop_fraction: float) -> str:
    scaled = round(stop_fraction * settings.order_tag.stop_fraction_scale)
    code = strategy_class(strategy_key).code
    return "-".join((ORDER_TAG_PREFIX, code, str(scaled), uuid4().hex[:8]))


def find_order_tag(value: str) -> OrderTag | None:
    parts = value.split("-")
    if parts[0] != ORDER_TAG_PREFIX:
        return None
    if len(parts) == 4:
        _, code, scaled, _ = parts
    elif len(parts) >= 6 and parts[2] in ORDER_KINDS:
        code, scaled = parts[1], parts[-2]
    else:
        return None
    found = STRATEGIES_BY_CODE.get(code)
    if found is None or not scaled.isascii() or not scaled.isdigit():
        return None
    return OrderTag(found.key, int(scaled) / settings.order_tag.stop_fraction_scale)
