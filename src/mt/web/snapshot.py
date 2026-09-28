from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Literal, TypedDict

from alpaca.trading.models import Order
from pydantic import Field

from mt.data.alpaca import AccountRead, Position
from mt.exchange import TRADING_ZONE
from mt.rules.values import StrategyKey
from mt.state import RunStatus, State, StateEvent


class BotState(TypedDict):
    status: RunStatus | Literal["unknown"]
    stale: bool
    running: bool
    reported: bool
    reportedAgoMinutes: float | None
    strategies: list[StrategyKey]
    paused: list[StrategyKey]
    events: list[StateEvent]


class SnapshotPosition(Position):
    unrealized_pnl_fraction: float = Field(exclude=True)
    unrealized_pnl_percent: float
    weight: float


class Snapshot(TypedDict):
    orders: list[Order]
    asOf: str
    equity: float
    cash: float
    buyingPower: float
    marketValue: float
    unrealized_pnl: float
    positions: Sequence[SnapshotPosition]


def build_snapshot(read: AccountRead) -> Snapshot:
    account = read.account
    positions = read.positions
    equity = round(account.equity, 2)
    held = snapshot_positions(positions, equity)
    return Snapshot(
        orders=read.orders,
        asOf=read.read_at.astimezone(TRADING_ZONE).strftime("%a %-d %b %Y, %H:%M:%S ET"),
        equity=equity,
        cash=round(account.cash, 2),
        buyingPower=round(account.buying_power, 2),
        marketValue=round(sum(row.value for row in held), 2),
        unrealized_pnl=round(sum(row.unrealized_pnl for row in held), 2),
        positions=held,
    )


def bot_state(state: State | None, heartbeat_timeout: timedelta) -> BotState:
    if state is None:
        return BotState(
            status="unknown",
            stale=True,
            running=False,
            reported=False,
            reportedAgoMinutes=None,
            strategies=[],
            paused=[],
            events=[],
        )
    silence = datetime.now(UTC) - state.heartbeat_at
    stale = silence > heartbeat_timeout
    return BotState(
        status=state.status,
        stale=stale,
        running=state.status == "running" and not stale,
        reported=True,
        reportedAgoMinutes=round(silence.total_seconds() / 60, 1),
        strategies=list(state.strategies),
        paused=list(state.paused),
        events=list(reversed(state.events)),
    )


def snapshot_positions(raw: list[Position], equity: float) -> list[SnapshotPosition]:
    rows = [
        SnapshotPosition(
            symbol=item.symbol,
            side=item.side,
            quantity=round(abs(item.quantity), 4),
            entry=round(item.entry, 4),
            last=round(item.last, 4),
            value=round(abs(item.value), 2),
            unrealized_pnl=round(item.unrealized_pnl, 2),
            unrealized_pnl_fraction=item.unrealized_pnl_fraction,
            unrealized_pnl_percent=round(item.unrealized_pnl_fraction * 100, 2),
            weight=round(abs(item.value) / equity * 100, 2) if equity else 0.0,
        )
        for item in raw
    ]
    rows.sort(key=lambda row: -row.value)
    return rows
