from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Literal, TypedDict

from alpaca.trading.models import Order
from pydantic import computed_field

from mt.config.values import StrategyKey
from mt.data.alpaca import AccountObservation, Position
from mt.exchange import TRADING_ZONE
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
    weight: float

    @computed_field
    @property
    def unrealized_pnl_percent(self) -> float:
        return round(self.unrealized_pnl_fraction * 100, 2)


class Snapshot(TypedDict):
    orders: list[Order]
    asOf: str
    equity: float
    cash: float
    buyingPower: float
    marketValue: float
    unrealized_pnl: float
    positions: Sequence[SnapshotPosition]


def build_snapshot(observation: AccountObservation) -> Snapshot:
    account = observation.account
    positions = observation.positions
    equity = round(account.equity, 2)
    held = snapshot_positions(positions, equity)
    return Snapshot(
        orders=observation.orders,
        asOf=observation.read_at.astimezone(TRADING_ZONE).strftime("%a %-d %b %Y, %H:%M:%S ET"),
        equity=equity,
        cash=round(account.cash, 2),
        buyingPower=round(account.buying_power, 2),
        marketValue=round(sum(row.value for row in held), 2),
        unrealized_pnl=round(sum(row.unrealized_pnl for row in held), 2),
        positions=held,
    )


def bot_state(state: State | None, heartbeat_timeout: timedelta) -> BotState:
    silence = datetime.now(UTC) - state.heartbeat_at if state else None
    stale = silence is None or silence > heartbeat_timeout
    running = state is not None and state.status == "running" and not stale
    return BotState(
        status=state.status if state else "unknown",
        stale=stale,
        running=running,
        reported=state is not None,
        reportedAgoMinutes=(
            round(silence.total_seconds() / 60, 1) if silence is not None else None
        ),
        strategies=list(state.strategies) if state else [],
        paused=list(state.paused) if state else [],
        events=list(reversed(state.events)) if state else [],
    )


def snapshot_positions(raw: list[Position], equity: float) -> list[SnapshotPosition]:
    rows = [
        SnapshotPosition(
            symbol=item.symbol,
            side="long" if item.side == "long" else "short",
            quantity=round(abs(item.quantity), 4),
            entry=round(item.entry, 4),
            last=round(item.last, 4),
            value=round(abs(item.value), 2),
            unrealized_pnl=round(item.unrealized_pnl, 2),
            unrealized_pnl_fraction=item.unrealized_pnl_fraction,
            weight=round(abs(item.value) / equity * 100, 2) if equity else 0.0,
        )
        for item in raw
    ]
    rows.sort(key=lambda row: -row.value)
    return rows
