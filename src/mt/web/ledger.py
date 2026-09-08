import asyncio
from bisect import bisect_left
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import TypedDict

import httpx

from mt.config.sections import RiskSection
from mt.config.values import StrategyKey, Symbol
from mt.data.alpaca import (
    AlpacaLiveClient,
    AlpacaPastClient,
    ClosedOrder,
    EquityPoint,
    Fill,
    Position,
)
from mt.exchange import TRADING_ZONE
from mt.snapshot import StateSnapshot
from mt.strategies.order_tag import UNATTRIBUTED, find_order_tag

from .pulse import BotState, PulsePosition, bot_state, pulse_positions
from .strategies import EntryWindow, entry_windows, strategy_labels


class FillRow(TypedDict):
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
    fills: list[FillRow]


class OpenCycle(TypedDict):
    strategy: str
    opened: str
    inDate: str
    inMinute: int
    fills: list[FillRow]


class Totals(TypedDict):
    n: int
    wins: int
    losses: int
    net: float
    gross: float
    bleed: float


class Day(TypedDict):
    date: str
    pnl: float
    trades: int
    wins: int
    before: float


@dataclass(slots=True)
class _Tally:
    direction: int
    opened: datetime
    strategy: StrategyKey | None
    in_quantity: float = 0.0
    in_value: float = 0.0
    out_quantity: float = 0.0
    out_value: float = 0.0
    fills: list[FillRow] = field(default_factory=list[FillRow])


EPSILON = 1e-9


def match_cycles(
    fills: list[Fill],
    orders: list[ClosedOrder],
) -> tuple[list[Cycle], dict[str, OpenCycle]]:
    strategies: dict[str, StrategyKey | None] = {
        order.id: _order_strategy(order.client_order_id or "") for order in orders
    }
    held: defaultdict[str, float] = defaultdict(float)
    tallies: dict[str, _Tally] = {}
    cycles: list[Cycle] = []

    for fill in sorted(fills, key=lambda row: row.transaction_time):
        symbol = fill.symbol
        quantity = fill.qty
        price = fill.price
        when = _trading_time(fill.transaction_time)
        signed = quantity if fill.side == "buy" else -quantity
        held[symbol] += signed

        cycle = tallies.get(symbol)
        if cycle is None:
            cycle = tallies[symbol] = _Tally(
                direction=1 if signed > 0 else -1,
                opened=when,
                strategy=strategies.get(fill.order_id),
            )

        entering = (signed > 0) == (cycle.direction > 0)
        cycle.fills.append(
            FillRow(
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
                cycle.strategy = strategies.get(fill.order_id)
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
        del tallies[symbol]

    still_open = {
        symbol: OpenCycle(
            strategy=cycle.strategy or UNATTRIBUTED,
            opened=f"{cycle.opened:%-d %b}",
            inDate=cycle.opened.date().isoformat(),
            inMinute=_clock_minute(cycle.opened),
            fills=cycle.fills,
        )
        for symbol, cycle in tallies.items()
    }
    return cycles, still_open


def totals(cycles: list[Cycle]) -> Totals:
    wins = [cycle for cycle in cycles if cycle["pnl"] > 0]
    losses = [cycle for cycle in cycles if cycle["pnl"] <= 0]
    return Totals(
        n=len(cycles),
        wins=len(wins),
        losses=len(losses),
        net=round(sum(cycle["pnl"] for cycle in cycles), 2),
        gross=round(sum(cycle["pnl"] for cycle in wins), 2),
        bleed=round(abs(sum(cycle["pnl"] for cycle in losses)), 2),
    )


def sessions(cycles: list[Cycle], closes: dict[str, float], opening: float) -> list[Day]:
    grouped: defaultdict[str, list[Cycle]] = defaultdict(list)
    for cycle in cycles:
        grouped[cycle["date"]].append(cycle)

    ordered = sorted(closes)
    days: list[Day] = []
    for day in sorted(grouped):
        position = bisect_left(ordered, day)
        before = closes[ordered[position - 1]] if position else opening
        days.append(
            Day(
                date=day,
                pnl=round(sum(cycle["pnl"] for cycle in grouped[day]), 2),
                trades=len(grouped[day]),
                wins=sum(1 for cycle in grouped[day] if cycle["pnl"] > 0),
                before=round(before, 2),
            )
        )
    return days


def _order_strategy(client_order_id: str) -> StrategyKey | None:
    tag = find_order_tag(client_order_id)
    return None if tag is None else tag.strategy


def _trading_time(timestamp: str) -> datetime:
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).astimezone(TRADING_ZONE)


def _clock_minute(when: datetime) -> int:
    return when.hour * 60 + when.minute


class PositionRow(PulsePosition):
    strategy: str
    opened: str
    inDate: str | None
    inMinute: int | None
    fills: list[FillRow]


class EquityDay(TypedDict):
    date: str
    equity: float


class IntradayPoint(TypedDict):
    t: str
    equity: float


class BenchmarkClose(TypedDict):
    date: str
    close: float


class Ledger(TypedDict):
    asOf: str
    today: str
    accountNumber: str
    status: str
    marketOpen: bool
    nextOpen: str
    invested: float
    funded: str
    equity: float
    lastEquity: float
    cash: float
    buyingPower: float
    marketValue: float
    unrealised: float
    positionCapPct: float
    dailyLossLimitPct: float
    bot: BotState
    strategies: list[dict[str, str]]
    windows: dict[str, EntryWindow]
    positions: list[PositionRow]
    trades: list[Cycle]
    days: list[Day]
    totals: Totals
    equityDaily: list[EquityDay]
    intraday: list[IntradayPoint]
    intradayDate: str
    benchmarkSymbol: str
    benchmark: list[BenchmarkClose]


async def build_ledger(
    live: AlpacaLiveClient,
    past: AlpacaPastClient,
    benchmark: Symbol,
    fallback_configuration: RiskSection,
    snapshot: StateSnapshot | None,
    stale: bool,
) -> Ledger:
    async with asyncio.TaskGroup() as reads:
        account_read = reads.create_task(live.account())
        positions_read = reads.create_task(live.positions())
        fills_read = reads.create_task(live.fills())
        orders_read = reads.create_task(live.closed_orders())
        daily_read = reads.create_task(live.equity("1A", "1D"))
        intraday_read = reads.create_task(live.equity("1D", "5Min"))
        clock_read = reads.create_task(live.clock())

    account = account_read.result()
    positions = positions_read.result()
    clock = clock_read.result()

    cycles, open_cycles = match_cycles(fills_read.result(), orders_read.result())
    equity_daily = _equity_series(daily_read.result())
    intraday_points, intraday_date = _intraday_series(intraday_read.result())

    invested = equity_daily[0]["equity"] if equity_daily else account.equity
    funded = equity_daily[0]["date"] if equity_daily else ""
    equity = round(account.equity, 2)
    closes = {row["date"]: row["equity"] for row in equity_daily}

    today = datetime.now(TRADING_ZONE).date().isoformat()
    if not equity_daily or equity_daily[-1]["date"] != today:
        equity_daily.append(EquityDay(date=today, equity=equity))

    rows = _position_rows(positions, equity, open_cycles)
    configuration = snapshot.configuration if snapshot else fallback_configuration
    benchmark_start = funded or today

    try:
        bars = await past.daily_bars(benchmark, benchmark_start)
    except httpx.HTTPError:
        bars = []

    return Ledger(
        asOf=datetime.now(TRADING_ZONE).strftime("%a %-d %b %Y, %H:%M:%S ET"),
        today=today,
        accountNumber=account.account_number,
        status=account.status,
        marketOpen=clock.is_open,
        nextOpen=datetime.fromisoformat(clock.next_open).strftime("%H:%M ET"),
        invested=invested,
        funded=datetime.fromisoformat(funded).strftime("%-d %b %Y") if funded else "—",
        equity=equity,
        lastEquity=round(account.last_equity, 2),
        cash=round(account.cash, 2),
        buyingPower=round(account.buying_power, 2),
        marketValue=round(sum(row["value"] for row in rows), 2),
        unrealised=round(sum(row["unreal"] for row in rows), 2),
        positionCapPct=round(100 * configuration.position_fraction_max, 2),
        dailyLossLimitPct=round(100 * configuration.per_day_max, 2),
        bot=bot_state(snapshot, stale),
        strategies=strategy_labels(),
        windows=entry_windows(),
        positions=rows,
        trades=cycles,
        days=sessions(cycles, closes, invested),
        totals=totals(cycles),
        equityDaily=equity_daily,
        intraday=intraday_points,
        intradayDate=intraday_date,
        benchmarkSymbol=benchmark,
        benchmark=[BenchmarkClose(date=bar.at[:10], close=bar.close) for bar in bars],
    )


def _funded_points(points: list[EquityPoint]) -> list[tuple[datetime, float]]:
    return [
        (datetime.fromtimestamp(point.timestamp, TRADING_ZONE), point.equity)
        for point in points
        if point.equity
    ]


def _equity_series(points: list[EquityPoint]) -> list[EquityDay]:
    return [
        EquityDay(date=when.date().isoformat(), equity=round(value, 2))
        for when, value in _funded_points(points)
    ]


def _intraday_series(points: list[EquityPoint]) -> tuple[list[IntradayPoint], str]:
    funded = _funded_points(points)
    rows = [
        IntradayPoint(t=when.strftime("%H:%M"), equity=round(value, 2)) for when, value in funded
    ]
    return rows, funded[0][0].date().isoformat() if funded else ""


def _position_rows(
    raw: list[Position],
    equity: float,
    open_cycles: dict[str, OpenCycle],
) -> list[PositionRow]:
    rows: list[PositionRow] = []
    for position in pulse_positions(raw, equity):
        held = open_cycles.get(position["symbol"])
        rows.append(
            PositionRow(
                **position,
                strategy=held["strategy"] if held else UNATTRIBUTED,
                opened=held["opened"] if held else "—",
                inDate=held["inDate"] if held else None,
                inMinute=held["inMinute"] if held else None,
                fills=held["fills"] if held else [],
            )
        )
    return rows
