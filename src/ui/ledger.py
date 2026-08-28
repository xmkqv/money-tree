from collections import defaultdict
from datetime import date, datetime
from typing import Any, TypedDict
from zoneinfo import ZoneInfo

from bot.attribution import find_order_strategy
from bot.types import STRATEGY_LABELS, StrategyName


TRADING_ZONE = ZoneInfo("America/New_York")
UNATTRIBUTED = "unattributed"
EPSILON = 1e-9


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
    heldMin: int


class Session(TypedDict):
    date: str
    pnl: float
    trades: int
    wins: int
    before: float


def order_engine(client_order_id: str) -> StrategyName | None:
    return find_order_strategy(client_order_id)


def _local(timestamp: str) -> datetime:
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).astimezone(TRADING_ZONE)


class OpenCycle(TypedDict):
    strategy: str
    opened: str


def match_cycles(
    fills: list[dict[str, Any]],
    orders: list[dict[str, Any]],
) -> tuple[list[Cycle], dict[str, OpenCycle]]:
    """Fold fills into position cycles — one trade per flat-to-flat round trip.

    A single position is usually opened and closed across many fills (fractional
    sizing splits every order), so matching fill-to-fill would report the same
    trade several times over. Attribution comes from the engine tag the bot puts
    on the opening order, and P&L is taken from raw cash flows rather than
    averaged prices so it stays exact.
    """
    engines = {
        order["id"]: order_engine(str(order.get("client_order_id") or "")) for order in orders
    }

    held: defaultdict[str, float] = defaultdict(float)
    live: dict[str, dict[str, Any]] = {}
    cycles: list[Cycle] = []

    for fill in sorted(fills, key=lambda f: str(f["transaction_time"])):
        symbol = str(fill["symbol"])
        qty = float(fill["qty"])
        price = float(fill["price"])
        when = _local(str(fill["transaction_time"]))
        signed = qty if fill["side"] == "buy" else -qty
        held[symbol] += signed

        cycle = live.get(symbol)
        if cycle is None:
            cycle = live[symbol] = {
                "direction": 1 if signed > 0 else -1,
                "in_qty": 0.0,
                "in_value": 0.0,
                "out_qty": 0.0,
                "out_value": 0.0,
                "opened": when,
                "engine": engines.get(str(fill["order_id"])),
            }

        if (signed > 0) == (cycle["direction"] > 0):
            cycle["in_qty"] += qty
            cycle["in_value"] += qty * price
            if cycle["engine"] is None:
                cycle["engine"] = engines.get(str(fill["order_id"]))
        else:
            cycle["out_qty"] += qty
            cycle["out_value"] += qty * price

        if abs(held[symbol]) > EPSILON:
            continue

        direction = int(cycle["direction"])
        pnl = (float(cycle["out_value"]) - float(cycle["in_value"])) * direction
        opened: datetime = cycle["opened"]
        cycles.append(
            Cycle(
                symbol=symbol,
                side="long" if direction > 0 else "short",
                strategy=cycle["engine"] or UNATTRIBUTED,
                qty=round(float(cycle["out_qty"]), 4),
                entry=round(float(cycle["in_value"]) / float(cycle["in_qty"]), 4),
                exit=round(float(cycle["out_value"]) / float(cycle["out_qty"]), 4),
                pnl=round(pnl, 2),
                date=when.date().isoformat(),
                minute=when.hour * 60 + when.minute,
                heldMin=max(0, int((when - opened).total_seconds() // 60)),
            )
        )
        del live[symbol]

    still_open = {
        symbol: OpenCycle(
            strategy=cycle["engine"] or UNATTRIBUTED,
            opened=f"{cycle['opened']:%-d %b}",
        )
        for symbol, cycle in live.items()
    }
    return cycles, still_open


def summarise(cycles: list[Cycle]) -> dict[str, Any]:
    wins = [c for c in cycles if c["pnl"] > 0]
    losses = [c for c in cycles if c["pnl"] <= 0]
    gross = sum(c["pnl"] for c in wins)
    bleed = abs(sum(c["pnl"] for c in losses))
    return {
        "n": len(cycles),
        "wins": len(wins),
        "losses": len(losses),
        "net": round(sum(c["pnl"] for c in cycles), 2),
        "gross": round(gross, 2),
        "bleed": round(bleed, 2),
    }


def sessions(cycles: list[Cycle], closes: dict[str, float], opening: float) -> list[Session]:
    """Realised P&L per trading day, each keyed to the equity it started from."""
    grouped: defaultdict[str, list[Cycle]] = defaultdict(list)
    for cycle in cycles:
        grouped[cycle["date"]].append(cycle)

    ordered = sorted(closes)
    out: list[Session] = []
    for day in sorted(grouped):
        earlier = [d for d in ordered if d < day]
        out.append(
            Session(
                date=day,
                pnl=round(sum(c["pnl"] for c in grouped[day]), 2),
                trades=len(grouped[day]),
                wins=sum(1 for c in grouped[day] if c["pnl"] > 0),
                before=round(closes[earlier[-1]] if earlier else opening, 2),
            )
        )
    return out


SHORT_LABELS: dict[str, str] = {
    "orb": "ORB5",
    "orb_momentum": "ORB10",
    "sma": "Momentum",
    "tfb_50": "TFB-50",
    UNATTRIBUTED: "Untagged",
}


def strategy_labels() -> list[dict[str, str]]:
    """Every engine the bot can tag, plus the catch-all for untagged orders."""
    labels = [
        {"id": name, "short": SHORT_LABELS[name], "label": STRATEGY_LABELS[name]}
        for name in STRATEGY_LABELS
        if name != "noop"
    ]
    labels.append({"id": UNATTRIBUTED, "short": "Untagged", "label": "No mt- order tag"})
    return labels


def parse_day(value: str) -> date:
    return date.fromisoformat(value)
