import re
from bisect import bisect_left
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, TypedDict
from zoneinfo import ZoneInfo

from bot.order_tag import find_order_tag
from bot.types import STRATEGY_LABELS, StrategyName


class Fill(TypedDict):
    d: str
    m: int
    p: float
    q: float
    s: str


class Cycle(TypedDict):
    symbol: str
    side: str
    strategy: str
    qty: float
    entry: float
    exit: float
    pnl: float
    date: str
    minute: int
    inDate: str
    inMinute: int
    heldMin: int
    fills: list[Fill]


class OpenCycle(TypedDict):
    strategy: str
    opened: str
    inDate: str
    inMinute: int
    fills: list[Fill]


class Session(TypedDict):
    date: str
    pnl: float
    trades: int
    wins: int
    before: float


@dataclass(slots=True)
class _LiveCycle:
    direction: int
    opened: datetime
    strategy: StrategyName | None
    in_quantity: float = 0.0
    in_value: float = 0.0
    out_quantity: float = 0.0
    out_value: float = 0.0
    fills: list[Fill] = field(default_factory=list[Fill])


TRADING_ZONE = ZoneInfo("America/New_York")
UNATTRIBUTED = "unattributed"
EPSILON = 1e-9
STRATEGY_IDS_BY_LABEL = {label: name for name, label in STRATEGY_LABELS.items()}
SHORT_LABELS: dict[str, str] = {
    "orb5": "ORB5",
    "orb10": "ORB10",
    "orb15": "ORB15",
    "sma": "Momentum SMA",
    "tfb_50": "TFB-50",
    UNATTRIBUTED: "Untagged",
}


def strategy_id(published: str) -> str:
    if published in STRATEGY_LABELS:
        return published
    return STRATEGY_IDS_BY_LABEL.get(published, published)


def label_order(label: str) -> tuple[str | int, ...]:
    """Alphabetical, but reading runs of digits as numbers, so ORB5 comes before ORB10."""
    return tuple(
        int(part) if part.isdigit() else part.casefold() for part in re.split(r"(\d+)", label)
    )


def strategy_labels() -> list[dict[str, str]]:
    """Every engine the page names, in the order it lists them.

    Sorted by the short label, because that is the name the reader sees and the
    order they look things up by. The untagged catch-all is appended rather than
    sorted: it is not an engine, so it belongs after all of them whatever it is
    called.
    """
    labels = sorted(
        (
            {"id": name, "short": SHORT_LABELS[name], "label": STRATEGY_LABELS[name]}
            for name in STRATEGY_LABELS
            if name != "noop"
        ),
        key=lambda entry: label_order(entry["short"]),
    )
    labels.append({"id": UNATTRIBUTED, "short": "Untagged", "label": "No mt- order tag"})
    return labels


def match_cycles(
    fills: list[dict[str, Any]],
    orders: list[dict[str, Any]],
) -> tuple[list[Cycle], dict[str, OpenCycle]]:
    strategies: dict[str, StrategyName | None] = {
        str(order["id"]): _order_strategy(str(order.get("client_order_id") or ""))
        for order in orders
    }
    held: defaultdict[str, float] = defaultdict(float)
    live: dict[str, _LiveCycle] = {}
    cycles: list[Cycle] = []

    for fill in sorted(fills, key=lambda row: str(row["transaction_time"])):
        symbol = str(fill["symbol"])
        quantity = float(fill["qty"])
        price = float(fill["price"])
        when = _trading_time(str(fill["transaction_time"]))
        signed = quantity if fill["side"] == "buy" else -quantity
        held[symbol] += signed

        cycle = live.get(symbol)
        if cycle is None:
            cycle = live[symbol] = _LiveCycle(
                direction=1 if signed > 0 else -1,
                opened=when,
                strategy=strategies.get(str(fill["order_id"])),
            )

        entering = (signed > 0) == (cycle.direction > 0)
        cycle.fills.append(
            Fill(
                d=when.date().isoformat(),
                m=_clock_minute(when),
                p=round(price, 4),
                q=round(quantity, 4),
                s="in" if entering else "out",
            )
        )
        if entering:
            cycle.in_quantity += quantity
            cycle.in_value += quantity * price
            if cycle.strategy is None:
                cycle.strategy = strategies.get(str(fill["order_id"]))
        else:
            cycle.out_quantity += quantity
            cycle.out_value += quantity * price

        if abs(held[symbol]) > EPSILON:
            continue

        cycles.append(
            Cycle(
                symbol=symbol,
                side="long" if cycle.direction > 0 else "short",
                strategy=cycle.strategy or UNATTRIBUTED,
                qty=round(cycle.out_quantity, 4),
                entry=round(cycle.in_value / cycle.in_quantity, 4),
                exit=round(cycle.out_value / cycle.out_quantity, 4),
                pnl=round((cycle.out_value - cycle.in_value) * cycle.direction, 2),
                date=when.date().isoformat(),
                minute=_clock_minute(when),
                inDate=cycle.opened.date().isoformat(),
                inMinute=_clock_minute(cycle.opened),
                heldMin=max(0, int((when - cycle.opened).total_seconds() // 60)),
                fills=cycle.fills,
            )
        )
        del live[symbol]

    still_open = {
        symbol: OpenCycle(
            strategy=cycle.strategy or UNATTRIBUTED,
            opened=f"{cycle.opened:%-d %b}",
            inDate=cycle.opened.date().isoformat(),
            inMinute=_clock_minute(cycle.opened),
            fills=cycle.fills,
        )
        for symbol, cycle in live.items()
    }
    return cycles, still_open


def totals(cycles: list[Cycle]) -> dict[str, Any]:
    wins = [cycle for cycle in cycles if cycle["pnl"] > 0]
    losses = [cycle for cycle in cycles if cycle["pnl"] <= 0]
    return {
        "n": len(cycles),
        "wins": len(wins),
        "losses": len(losses),
        "net": round(sum(cycle["pnl"] for cycle in cycles), 2),
        "gross": round(sum(cycle["pnl"] for cycle in wins), 2),
        "bleed": round(abs(sum(cycle["pnl"] for cycle in losses)), 2),
    }


def sessions(cycles: list[Cycle], closes: dict[str, float], opening: float) -> list[Session]:
    grouped: defaultdict[str, list[Cycle]] = defaultdict(list)
    for cycle in cycles:
        grouped[cycle["date"]].append(cycle)

    ordered = sorted(closes)
    days: list[Session] = []
    for day in sorted(grouped):
        position = bisect_left(ordered, day)
        before = closes[ordered[position - 1]] if position else opening
        days.append(
            Session(
                date=day,
                pnl=round(sum(cycle["pnl"] for cycle in grouped[day]), 2),
                trades=len(grouped[day]),
                wins=sum(1 for cycle in grouped[day] if cycle["pnl"] > 0),
                before=round(before, 2),
            )
        )
    return days


def parse_day(value: str) -> date:
    return date.fromisoformat(value)


def _order_strategy(client_order_id: str) -> StrategyName | None:
    tag = find_order_tag(client_order_id)
    return None if tag is None else tag.strategy


def _trading_time(timestamp: str) -> datetime:
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).astimezone(TRADING_ZONE)


def _clock_minute(when: datetime) -> int:
    return when.hour * 60 + when.minute
