from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Literal, TypedDict

from alpaca.trading.enums import OrderType
from alpaca.trading.models import Order

from mt.data.alpaca import AccountRead, Position
from mt.rules.values import STRATEGY_KEYS, UNATTRIBUTED, OrderReason, StrategyKey, Unattributed
from mt.state import RunStatus, State, StateEvent
from mt.strategies.registry import find_order_reason, find_order_strategy_key


type Selection = Literal["online", "paused", "unselected", "unknown"]


class BotState(TypedDict):
    status: RunStatus | Literal["unknown"]
    isStale: bool
    isRunning: bool
    isReported: bool
    reportedAgoMinutes: float | None
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


class OrderRow(TypedDict):
    symbol: str | None
    side: str | None
    quantity: float | None
    type: str | None
    limit: float | None
    stop: float | None
    status: str
    strategy_key: StrategyKey | Unattributed
    reason: OrderReason | None


class Snapshot(TypedDict):
    orders: list[OrderRow]
    readAt: str
    equity: float
    cash: float
    buyingPower: float
    marketValue: float
    unrealized_pnl: float
    positions: Sequence[SnapshotPosition]


STOP_ORDER_TYPES = frozenset({OrderType.STOP, OrderType.STOP_LIMIT, OrderType.TRAILING_STOP})


def build_snapshot(read: AccountRead) -> Snapshot:
    account = read.account
    equity = round(account.equity, 2)
    held = _snapshot_positions(read.positions, equity)
    return Snapshot(
        orders=[_order_row(order) for order in read.orders],
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
        selection=selection,
        events=list(reversed(state.events)),
    )


def order_reason(order: Order) -> OrderReason | None:
    found = find_order_reason(order.client_order_id)
    if found is None and order.type in STOP_ORDER_TYPES:
        return "stop"
    return found


def _order_row(order: Order) -> OrderRow:
    return OrderRow(
        symbol=order.symbol,
        side=_name(order.side),
        quantity=_price(order.qty),
        type=_name(order.type),
        limit=_price(order.limit_price),
        stop=_price(order.stop_price),
        status=order.status.value,
        strategy_key=find_order_strategy_key(order.client_order_id) or UNATTRIBUTED,
        reason=order_reason(order),
    )


def _price(value: str | float | None) -> float | None:
    return None if value is None else round(float(value), 4)


def _name(value: Enum | None) -> str | None:
    return None if value is None else str(value.value)


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
