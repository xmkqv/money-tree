import asyncio
from bisect import bisect_left
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import TypedDict

from mt.data.alpaca import (
    AccountRead,
    ClosedOrder,
    EquityPoint,
    Fill,
    TradingClientAlpaca,
)
from mt.data.asset import Asset
from mt.data.bars import BarsClientAlpaca
from mt.exchange import TRADING_ZONE, trading_time
from mt.rules.sections import DashboardSection
from mt.rules.values import UNATTRIBUTED, StrategyKey, Symbol, Unattributed
from mt.sizing import Direction
from mt.strategies.order_tag import find_order_strategy_key

from .snapshot import Snapshot, SnapshotPosition, build_snapshot
from .strategies import StrategyLabel, strategy_labels


class FillRow(TypedDict):
    d: str
    m: int
    p: float
    quantity: float
    s: str


class Trade(TypedDict):
    symbol: str
    side: str
    strategy_key: StrategyKey | Unattributed
    quantity: float
    entry: float
    exit: float
    pnl: float
    date: str
    minute: int
    entered_at: str
    duration_minutes: int
    fills: list[FillRow]


class OpenTrade(TypedDict):
    strategy_key: StrategyKey | Unattributed
    entered_at: str
    fills: list[FillRow]


class Totals(TypedDict):
    n: int
    wins: int
    losses: int
    net_pnl: float
    gross_profit: float
    gross_loss: float


class Day(TypedDict):
    date: str
    pnl: float
    trades: int
    wins: int
    before: float


class PositionRow(SnapshotPosition):
    strategy_key: StrategyKey | Unattributed
    entered_at: str | None
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
    baseline: float | None
    benchmarkPct: float | None
    equityIndex: int


class Ledger(Snapshot):
    periods: dict[str, Period]
    today: str
    accountNumber: str
    status: str
    marketOpen: bool
    nextOpen: str
    nextClose: str
    invested: float
    funded: str
    lastEquity: float
    strategies: list[StrategyLabel]
    trades: list[Trade]
    days: list[Day]
    totals: Totals
    equityDaily: list[EquityDay]
    intraday: list[IntradayPoint]
    intradayDate: str
    benchmarkSymbol: str
    benchmark: list[BenchmarkClose]


@dataclass(slots=True)
class _Tally:
    direction: Direction
    entered_at: datetime
    strategy_key: StrategyKey | None
    in_quantity: float = 0.0
    in_value: float = 0.0
    out_quantity: float = 0.0
    out_value: float = 0.0
    fills: list[FillRow] = field(default_factory=list[FillRow])


def match_trades(
    fills: tuple[Fill, ...],
    orders: tuple[ClosedOrder, ...],
    flat_quantity_max: float,
) -> tuple[list[Trade], dict[str, OpenTrade]]:
    strategies: dict[str, StrategyKey | None] = {
        order.id: find_order_strategy_key(order.client_order_id or "") for order in orders
    }
    held: defaultdict[str, float] = defaultdict(float)
    tallies: dict[str, _Tally] = {}
    trades: list[Trade] = []

    pending_fills = sorted(fills, key=lambda row: row.transaction_time, reverse=True)
    while pending_fills:
        fill = pending_fills.pop()
        symbol = fill.symbol
        quantity = fill.quantity
        price = fill.price
        when = trading_time(fill.transaction_time)
        signed = quantity if fill.side == "buy" else -quantity
        current = held[symbol]
        if current * signed < 0 and quantity > abs(current) + flat_quantity_max:
            pending_fills.append(fill.model_copy(update={"quantity": quantity - abs(current)}))
            quantity = abs(current)
            signed = quantity if fill.side == "buy" else -quantity
        held[symbol] += signed

        trade = tallies.get(symbol)
        if trade is None:
            trade = tallies[symbol] = _Tally(
                direction=1 if signed > 0 else -1,
                entered_at=when,
                strategy_key=strategies.get(fill.order_id),
            )

        entering = (signed > 0) == (trade.direction > 0)
        trade.fills.append(
            FillRow(
                d=when.date().isoformat(),
                m=_clock_minute(when),
                p=round(price, 4),
                quantity=round(quantity, 4),
                s="in" if entering else "out",
            )
        )
        if entering:
            trade.in_quantity += quantity
            trade.in_value += quantity * price
            if trade.strategy_key is None:
                trade.strategy_key = strategies.get(fill.order_id)
        else:
            trade.out_quantity += quantity
            trade.out_value += quantity * price

        if abs(held[symbol]) > flat_quantity_max:
            continue

        trades.append(
            Trade(
                symbol=symbol,
                side="long" if trade.direction > 0 else "short",
                strategy_key=trade.strategy_key or UNATTRIBUTED,
                quantity=round(trade.out_quantity, 4),
                entry=round(trade.in_value / trade.in_quantity, 4),
                exit=round(trade.out_value / trade.out_quantity, 4),
                pnl=round((trade.out_value - trade.in_value) * trade.direction, 2),
                date=when.date().isoformat(),
                minute=_clock_minute(when),
                entered_at=trade.entered_at.isoformat(),
                duration_minutes=max(
                    0, int((when.timestamp() - trade.entered_at.timestamp()) // 60)
                ),
                fills=trade.fills,
            )
        )
        del tallies[symbol]
        held[symbol] = 0.0

    still_open = {
        symbol: OpenTrade(
            strategy_key=trade.strategy_key or UNATTRIBUTED,
            entered_at=trade.entered_at.isoformat(),
            fills=trade.fills,
        )
        for symbol, trade in tallies.items()
    }
    return trades, still_open


def totals(trades: list[Trade]) -> Totals:
    wins = [trade for trade in trades if trade["pnl"] > 0]
    losses = [trade for trade in trades if trade["pnl"] <= 0]
    return Totals(
        n=len(trades),
        wins=len(wins),
        losses=len(losses),
        net_pnl=round(sum(trade["pnl"] for trade in trades), 2),
        gross_profit=round(sum(trade["pnl"] for trade in wins), 2),
        gross_loss=round(abs(sum(trade["pnl"] for trade in losses)), 2),
    )


def days(trades: list[Trade], closes: dict[str, float], opening: float) -> list[Day]:
    grouped: defaultdict[str, list[Trade]] = defaultdict(list)
    for trade in trades:
        grouped[trade["date"]].append(trade)

    ordered = sorted(closes)
    days: list[Day] = []
    for day in sorted(grouped):
        index = bisect_left(ordered, day)
        before = closes[ordered[index - 1]] if index else opening
        days.append(
            Day(
                date=day,
                pnl=round(sum(trade["pnl"] for trade in grouped[day]), 2),
                trades=len(grouped[day]),
                wins=sum(1 for trade in grouped[day] if trade["pnl"] > 0),
                before=round(before, 2),
            )
        )
    return days


def _clock_minute(when: datetime) -> int:
    return when.hour * 60 + when.minute


async def build_ledger(
    read: AccountRead,
    trading: TradingClientAlpaca,
    bars_client: BarsClientAlpaca,
    benchmark: Symbol,
    dashboard: DashboardSection,
    match_history: Callable[
        [tuple[Fill, ...], tuple[ClosedOrder, ...], float],
        tuple[list[Trade], dict[str, OpenTrade]],
    ],
) -> Ledger:
    async with asyncio.TaskGroup() as reads:
        history_read = reads.create_task(trading.history())
        daily_read = reads.create_task(trading.daily_equity())
        intraday_read = reads.create_task(
            trading.equity(dashboard.equity_intraday_period, dashboard.equity_intraday_timeframe)
        )
        clock_read = reads.create_task(trading.clock())

    account = read.account
    snapshot = build_snapshot(read)
    clock = clock_read.result()

    trades, open_trades = match_history(
        history_read.result().fills, history_read.result().orders, dashboard.flat_quantity_max
    )
    equity_daily = _equity_series(daily_read.result())
    intraday_points, intraday_date = _intraday_series(intraday_read.result())

    funded_index = next(
        (index for index, row in enumerate(equity_daily) if row["equity"]), len(equity_daily)
    )
    equity_daily = equity_daily[funded_index:]
    first_funded = equity_daily[0] if equity_daily else None
    invested = first_funded["equity"] if first_funded is not None else account.equity
    funded = first_funded["date"] if first_funded is not None else ""
    equity = round(account.equity, 2)
    closes = {row["date"]: row["equity"] for row in equity_daily}

    today = datetime.now(TRADING_ZONE).date().isoformat()
    periods_equity = list(equity_daily)
    if not equity_daily or equity_daily[-1]["date"] != today:
        equity_daily.append(EquityDay(date=today, equity=equity))

    rows = _position_rows(snapshot["positions"], open_trades)
    benchmark_start = funded or today

    asset = Asset.from_symbol(benchmark)
    bars = (
        await bars_client.bars(
            [asset],
            "1Day",
            datetime.fromisoformat(benchmark_start),
            limit=dashboard.bars_max,
            pages_max=1,
        )
    )[asset]

    benchmark_closes = [BenchmarkClose(date=bar.opened_at[:10], close=bar.close) for bar in bars]
    return {
        **snapshot,
        "periods": calendar_periods(date.fromisoformat(today), periods_equity, benchmark_closes),
        "today": today,
        "accountNumber": account.account_number,
        "status": account.status,
        "marketOpen": clock.is_open,
        "nextOpen": trading_time(clock.next_open).strftime("%H:%M ET"),
        "nextClose": trading_time(clock.next_close).strftime("%H:%M ET"),
        "invested": invested,
        "funded": datetime.fromisoformat(funded).strftime("%-d %b %Y") if funded else "—",
        "lastEquity": round(account.last_equity, 2),
        "strategies": strategy_labels(),
        "positions": rows,
        "trades": trades,
        "days": days(trades, closes, invested),
        "totals": totals(trades),
        "equityDaily": equity_daily,
        "intraday": intraday_points,
        "intradayDate": intraday_date,
        "benchmarkSymbol": benchmark,
        "benchmark": benchmark_closes,
    }


def calendar_periods(
    today: date, equity: list[EquityDay], benchmark: list[BenchmarkClose]
) -> dict[str, Period]:
    opened_on = {"W": today - timedelta(days=today.weekday()), "M": today.replace(day=1)}
    equity_dates = [row["date"] for row in equity]
    benchmark_dates = [row["date"] for row in benchmark]
    periods: dict[str, Period] = {}
    for key, opened in opened_on.items():
        start = opened.isoformat()
        index = max(0, bisect_left(equity_dates, start) - 1)
        baseline = equity[index]["equity"] if equity else None
        bench_index = max(0, bisect_left(benchmark_dates, start) - 1)
        benchmark_baseline = benchmark[bench_index]["close"] if benchmark else None
        periods[key] = Period(
            start=start,
            baseline=baseline,
            equityIndex=index,
            benchmarkPct=(benchmark[-1]["close"] / benchmark_baseline - 1) * 100
            if benchmark_baseline
            else None,
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
    raw: Sequence[SnapshotPosition],
    open_trades: dict[str, OpenTrade],
) -> list[PositionRow]:
    return [
        PositionRow(
            **position.model_dump(),
            strategy_key=held["strategy_key"]
            if (held := open_trades.get(position.symbol))
            else UNATTRIBUTED,
            entered_at=held["entered_at"] if held else None,
            fills=held["fills"] if held else [],
        )
        for position in raw
    ]
