from dataclasses import dataclass
from typing import Literal, cast
from uuid import uuid4

from .types import StrategyName


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
ORDER_KINDS: frozenset[str] = frozenset({"e", "s", "x"})
# One letter each, and these letters never change: they are written into the client order id
# of every order the bot places, so the broker's own record is read back through them.
STRATEGY_CODES: dict[StrategyName, str] = {
    "noop": "n",
    "orb5": "o",
    "sma": "s",
    "tfb_50": "t",
    "orb10": "m",
}
STRATEGIES_BY_CODE: dict[str, StrategyName] = {
    code: strategy for strategy, code in STRATEGY_CODES.items()
}


def order_tag(strategy: StrategyName, kind: OrderKind, signal: str, risk_fraction: float) -> str:
    scaled = round(risk_fraction * RISK_FRACTION_SCALE)
    return "-".join(
        (ORDER_TAG_PREFIX, STRATEGY_CODES[strategy], kind, signal, str(scaled), uuid4().hex[:8])
    )


def find_order_tag(value: str) -> OrderTag | None:
    parts = value.split("-")
    if len(parts) != ORDER_TAG_PARTS or parts[0] != ORDER_TAG_PREFIX:
        return None
    strategy = STRATEGIES_BY_CODE.get(parts[1])
    if strategy is None or parts[2] not in ORDER_KINDS or not parts[4].isdigit():
        return None
    return OrderTag(
        strategy,
        cast(OrderKind, parts[2]),
        parts[3],
        int(parts[4]) / RISK_FRACTION_SCALE,
    )
