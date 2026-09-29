from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Literal, TypedDict

from alpaca.trading.models import Order

from mt.data.alpaca import AccountRead, Position
from mt.rules.values import STRATEGY_KEYS, StrategyKey
from mt.state import RunStatus, State, StateEvent


type Selection = Literal["online", "paused", "unselected", "unknown"]


class BotState(TypedDict):
    status: RunStatus | Literal["unknown"]
    isStale: bool
    isRunning: bool
    isReported: bool
    reportedAgoMinutes: float | None
    strategies: list[StrategyKey]
    paused: list[StrategyKey]
    selection: dict[StrategyKey, Selection]
    events: list[StateEvent]


class SnapshotPosition(TypedDict):
    symbol: str
    side: Literal["long", "short"]
    quantity: float
    entry: float
    last: float
    value: float
    unrealized_pnl: float
    unrealized_pnl_percent: float
    weight: float | None


class Snapshot(TypedDict):
    orders: list[Order]
    readAt: str
    equity: float
    cash: float
    buyingPower: float
    marketValue: float
    unrealized_pnl: float
    positions: Sequence[SnapshotPosition]


def build_snapshot(read: AccountRead) -> Snapshot:
    account = read.account
    equity = round(account.equity, 2)
    held = _snapshot_positions(read.positions, equity)
    return Snapshot(
        orders=read.orders,
        readAt=read.read_at.isoformat(),
        equity=equity,
        cash=round(account.cash, 2),
        buyingPower=round(account.buying_power, 2),
        marketValue=round(sum(row["value"] for row in held), 2),
        unrealized_pnl=round(sum(row["unrealized_pnl"] for row in held), 2),
        positions=held,
    )


def bot_state(state: State | None, heartbeat_timeout: timedelta) -> BotState:
    selection: dict[StrategyKey, Selection] = {key: _selection(state, key) for key in STRATEGY_KEYS}
    if state is None:
        return BotState(
            status="unknown",
            isStale=True,
            isRunning=False,
            isReported=False,
            reportedAgoMinutes=None,
            strategies=[],
            paused=[],
            selection=selection,
            events=[],
        )
    silence = datetime.now(UTC) - state.heartbeat_at
    is_stale = silence > heartbeat_timeout
    return BotState(
        status=state.status,
        isStale=is_stale,
        isRunning=state.status == "running" and not is_stale,
        isReported=True,
        reportedAgoMinutes=round(silence.total_seconds() / 60, 1),
        strategies=list(state.strategies),
        paused=list(state.paused),
        selection=selection,
        events=list(reversed(state.events)),
    )


def _selection(state: State | None, key: StrategyKey) -> Selection:
    if state is None:
        return "unknown"
    if key not in state.strategies:
        return "unselected"
    if key in state.paused:
        return "paused"
    return "online"


def _snapshot_positions(raw: list[Position], equity: float) -> list[SnapshotPosition]:
    return sorted(
        (
            SnapshotPosition(
                symbol=item.symbol,
                side=item.side,
                quantity=round(abs(item.quantity), 4),
                entry=round(item.entry, 4),
                last=round(item.last, 4),
                value=round(abs(item.value), 2),
                unrealized_pnl=round(item.unrealized_pnl, 2),
                unrealized_pnl_percent=round(item.unrealized_pnl_fraction * 100, 2),
                weight=round(abs(item.value) / equity * 100, 2) if equity else None,
            )
            for item in raw
        ),
        key=lambda row: -row["value"],
    )
