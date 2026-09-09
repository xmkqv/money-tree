import asyncio
from bisect import bisect_left
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import TypedDict

from alpaca.trading.models import Order

from mt.config.sections import DashboardSection
from mt.config.values import StrategyKey, Symbol
from mt.data.alpaca import (
    AlpacaLiveClient,
    AlpacaPastClient,
    ClosedOrder,
    EquityPoint,
    Fill,
    Position,
)
from mt.exchange import TRADING_ZONE, trading_time
from mt.strategies.order_tag import UNATTRIBUTED, find_order_tag

from .pulse import PulsePosition, pulse_positions
from .strategies import StrategyLabel, strategy_labels


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


class Period(TypedDict):
    start: str
    base: float | None
    benchmarkPct: float | None
    equityIndex: int


class Ledger(TypedDict):
    periods: dict[str, Period]
    orders: list[Order]
    asOf: str
    today: str
    accountNumber: str
    status: str
    marketOpen: bool
    nextOpen: str
    nextClose: str
    invested: float
    funded: str
    equity: float
    lastEquity: float
    cash: float
    buyingPower: float
    marketValue: float
    unrealised: float
    strategies: list[StrategyLabel]
    positions: list[PositionRow]
    trades: list[Cycle]
    days: list[Day]
    totals: Totals
    equityDaily: list[EquityDay]
    intraday: list[IntradayPoint]
    intradayDate: str
    benchmarkSymbol: str
    benchmark: list[BenchmarkClose]


@dataclass(slots=True)
class _Tally:
    direction: int
    opened_at: datetime
    strategy: StrategyKey | None
    in_quantity: float = 0.0
    in_value: float = 0.0
    out_quantity: float = 0.0
    out_value: float = 0.0
    fills: list[FillRow] = field(default_factory=list[FillRow])


def match_cycles(
    fills: list[Fill],
    orders: list[ClosedOrder],
    flat_quantity_max: float,
) -> tuple[list[Cycle], dict[str, OpenCycle]]:
    strategies: dict[str, StrategyKey | None] = {
        order.id: _order_strategy(order.client_order_id or "") for order in orders
    }
    held: defaultdict[str, float] = defaultdict(float)
    tallies: dict[str, _Tally] = {}
    cycles: list[Cycle] = []

    pending_fills = sorted(fills, key=lambda row: row.transaction_time, reverse=True)
    while pending_fills:
        fill = pending_fills.pop()
        symbol = fill.symbol
        quantity = fill.qty
        price = fill.price
        when = trading_time(fill.transaction_time)
        signed = quantity if fill.side == "buy" else -quantity
        current = held[symbol]
        if current * signed < 0 and quantity > abs(current) + flat_quantity_max:
            pending_fills.append(fill.model_copy(update={"qty": quantity - abs(current)}))
            quantity = abs(current)
            signed = quantity if fill.side == "buy" else -quantity
        held[symbol] += signed

        cycle = tallies.get(symbol)
        if cycle is None:
            cycle = tallies[symbol] = _Tally(
                direction=1 if signed > 0 else -1,
                opened_at=when,
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

        if abs(held[symbol]) > flat_quantity_max:
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
                inDate=cycle.opened_at.date().isoformat(),
                inMinute=_clock_minute(cycle.opened_at),
                heldMin=max(0, int((when - cycle.opened_at).total_seconds() // 60)),
                fills=cycle.fills,
            )
        )
        del tallies[symbol]
        held[symbol] = 0.0

    still_open = {
        symbol: OpenCycle(
            strategy=cycle.strategy or UNATTRIBUTED,
            opened=f"{cycle.opened_at:%-d %b}",
            inDate=cycle.opened_at.date().isoformat(),
            inMinute=_clock_minute(cycle.opened_at),
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


def days(cycles: list[Cycle], closes: dict[str, float], opening: float) -> list[Day]:
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


def _clock_minute(when: datetime) -> int:
    return when.hour * 60 + when.minute


async def build_ledger(
    live: AlpacaLiveClient,
    past: AlpacaPastClient,
    benchmark: Symbol,
    dashboard: DashboardSection,
) -> Ledger:
    async with asyncio.TaskGroup() as reads:
        open_orders_read = reads.create_task(live.open_orders())
        account_read = reads.create_task(live.account())
        positions_read = reads.create_task(live.positions())
        fills_read = reads.create_task(live.fills())
        orders_read = reads.create_task(live.closed_orders())
        daily_read = reads.create_task(
            live.equity(dashboard.equity_daily_period, dashboard.equity_daily_timeframe)
        )
        intraday_read = reads.create_task(
            live.equity(dashboard.equity_intraday_period, dashboard.equity_intraday_timeframe)
        )
        clock_read = reads.create_task(live.clock())

    account = account_read.result()
    positions = positions_read.result()
    clock = clock_read.result()

    cycles, open_cycles = match_cycles(
        fills_read.result(), orders_read.result(), dashboard.flat_quantity_max
    )
    equity_daily = _equity_series(daily_read.result())
    intraday_points, intraday_date = _intraday_series(intraday_read.result())

    funding = next((row for row in equity_daily if row["equity"]), None)
    invested = funding["equity"] if funding is not None else account.equity
    funded = funding["date"] if funding is not None else ""
    equity = round(account.equity, 2)
    closes = {row["date"]: row["equity"] for row in equity_daily}

    today = datetime.now(TRADING_ZONE).date().isoformat()
    periods_equity = list(equity_daily)
    if not equity_daily or equity_daily[-1]["date"] != today:
        equity_daily.append(EquityDay(date=today, equity=equity))

    rows = _position_rows(positions, equity, open_cycles)
    benchmark_start = funded or today

    bars = await past.daily_bars(benchmark, benchmark_start)

    benchmark_closes = [BenchmarkClose(date=bar.opened_at[:10], close=bar.close) for bar in bars]
    return Ledger(
        periods=calendar_periods(date.fromisoformat(today), periods_equity, benchmark_closes),
        orders=open_orders_read.result(),
        asOf=datetime.now(TRADING_ZONE).strftime("%a %-d %b %Y, %H:%M:%S ET"),
        today=today,
        accountNumber=account.account_number,
        status=account.status,
        marketOpen=clock.is_open,
        nextOpen=trading_time(clock.next_open).strftime("%H:%M ET"),
        nextClose=trading_time(clock.next_close).strftime("%H:%M ET"),
        invested=invested,
        funded=datetime.fromisoformat(funded).strftime("%-d %b %Y") if funded else "—",
        equity=equity,
        lastEquity=round(account.last_equity, 2),
        cash=round(account.cash, 2),
        buyingPower=round(account.buying_power, 2),
        marketValue=round(sum(row["value"] for row in rows), 2),
        unrealised=round(sum(row["unreal"] for row in rows), 2),
        strategies=strategy_labels(),
        positions=rows,
        trades=cycles,
        days=days(cycles, closes, invested),
        totals=totals(cycles),
        equityDaily=equity_daily,
        intraday=intraday_points,
        intradayDate=intraday_date,
        benchmarkSymbol=benchmark,
        benchmark=benchmark_closes,
    )


def calendar_periods(
    today: date, equity: list[EquityDay], benchmark: list[BenchmarkClose]
) -> dict[str, Period]:
    boundaries = {"W": today - timedelta(days=today.weekday()), "M": today.replace(day=1)}
    equity_dates = [row["date"] for row in equity]
    benchmark_dates = [row["date"] for row in benchmark]
    periods: dict[str, Period] = {}
    for key, boundary in boundaries.items():
        start = boundary.isoformat()
        index = max(0, bisect_left(equity_dates, start) - 1)
        base = equity[index]["equity"] if equity else None
        bench_index = max(0, bisect_left(benchmark_dates, start) - 1)
        bench_base = benchmark[bench_index]["close"] if benchmark else None
        periods[key] = Period(
            start=start,
            base=base,
            equityIndex=index,
            benchmarkPct=(benchmark[-1]["close"] / bench_base - 1) * 100 if bench_base else None,
        )
    return periods


def _zoned_points(points: list[EquityPoint]) -> list[tuple[datetime, float]]:
    return [
        (datetime.fromtimestamp(point.timestamp, TRADING_ZONE), point.equity) for point in points
    ]


def _equity_series(points: list[EquityPoint]) -> list[EquityDay]:
    return [
        EquityDay(date=when.date().isoformat(), equity=round(value, 2))
        for when, value in _zoned_points(points)
    ]


def _intraday_series(points: list[EquityPoint]) -> tuple[list[IntradayPoint], str]:
    zoned = _zoned_points(points)
    rows = [
        IntradayPoint(t=when.strftime("%H:%M"), equity=round(value, 2)) for when, value in zoned
    ]
    return rows, zoned[0][0].date().isoformat() if zoned else ""


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
