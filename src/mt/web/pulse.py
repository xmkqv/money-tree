import asyncio
from datetime import datetime
from typing import TypedDict

from alpaca.trading.models import Order

from mt.data.alpaca import AlpacaLiveClient, Position
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
    qty: float
    entry: float
    last: float
    value: float
    unreal: float
    unrealPct: float
    weight: float


class Pulse(TypedDict):
    orders: list[Order]
    asOf: str
    equity: float
    cash: float
    buyingPower: float
    marketValue: float
    unrealised: float
    positions: list[PulsePosition]


async def build_pulse(live: AlpacaLiveClient) -> Pulse:
    async with asyncio.TaskGroup() as reads:
        open_orders_read = reads.create_task(live.open_orders())
        account_read = reads.create_task(live.account())
        positions_read = reads.create_task(live.positions())

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
        unrealised=round(sum(row["unreal"] for row in held), 2),
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
            qty=round(abs(item.qty), 4),
            entry=round(item.avg_entry_price, 4),
            last=round(item.current_price, 4),
            value=round(abs(item.market_value), 2),
            unreal=round(item.unrealized_pl, 2),
            unrealPct=round(item.unrealized_plpc * 100, 2),
            weight=round(abs(item.market_value) / equity * 100, 2) if equity else 0.0,
        )
        for item in raw
    ]
    rows.sort(key=lambda row: -row["value"])
    return rows
