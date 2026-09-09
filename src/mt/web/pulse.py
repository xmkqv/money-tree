import asyncio
from datetime import datetime
from typing import TypedDict

from alpaca.trading.models import Order

from mt.data.alpaca import Position, TradingClientAlpaca
from mt.exchange import TRADING_ZONE
from mt.snapshot import StateEvent, StateSnapshot


class BotState(TypedDict):
    status: str
    stale: bool
    running: bool
    reported: bool
    strategies: list[str]
    paused: list[str]
    events: list[StateEvent]


class PulsePosition(TypedDict):
    symbol: str
    side: str
    quantity: float
    entry: float
    last: float
    value: float
    unrealized_pnl: float
    unrealized_pnl_percent: float
    weight: float


class Pulse(TypedDict):
    orders: list[Order]
    asOf: str
    equity: float
    cash: float
    buyingPower: float
    marketValue: float
    unrealized_pnl: float
    positions: list[PulsePosition]


async def build_pulse(trading: TradingClientAlpaca) -> Pulse:
    async with asyncio.TaskGroup() as reads:
        open_orders_read = reads.create_task(trading.open_orders())
        account_read = reads.create_task(trading.account())
        positions_read = reads.create_task(trading.positions())

    account = account_read.result()
    positions = positions_read.result()
    equity = round(account.equity, 2)
    held = pulse_positions(positions, equity)
    return Pulse(
        orders=open_orders_read.result(),
        asOf=datetime.now(TRADING_ZONE).strftime("%a %-d %b %Y, %H:%M:%S ET"),
        equity=equity,
        cash=round(account.cash, 2),
        buyingPower=round(account.buying_power, 2),
        marketValue=round(sum(row["value"] for row in held), 2),
        unrealized_pnl=round(sum(row["unrealized_pnl"] for row in held), 2),
        positions=held,
    )


def bot_state(snapshot: StateSnapshot | None, stale: bool) -> BotState:
    running = snapshot is not None and snapshot.status == "running" and not stale
    return BotState(
        status=snapshot.status if snapshot else "unknown",
        stale=stale,
        running=running,
        reported=snapshot is not None,
        strategies=list(snapshot.strategies) if snapshot else [],
        paused=list(snapshot.paused) if snapshot else [],
        events=list(reversed(snapshot.events)) if snapshot else [],
    )


def pulse_positions(raw: list[Position], equity: float) -> list[PulsePosition]:
    rows = [
        PulsePosition(
            symbol=item.symbol,
            side="long" if item.side == "long" else "short",
            quantity=round(abs(item.quantity), 4),
            entry=round(item.avg_entry_price, 4),
            last=round(item.current_price, 4),
            value=round(abs(item.market_value), 2),
            unrealized_pnl=round(item.unrealized_pnl, 2),
            unrealized_pnl_percent=round(item.unrealized_pnl_fraction * 100, 2),
            weight=round(abs(item.market_value) / equity * 100, 2) if equity else 0.0,
        )
        for item in raw
    ]
    rows.sort(key=lambda row: -row["value"])
    return rows
