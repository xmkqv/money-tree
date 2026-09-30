import asyncio
from bisect import bisect_left
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from itertools import dropwhile
from typing import TypedDict

from alpaca.trading.models import Order

from mt.data.alpaca import AccountRead, EquityPoint, Fill, TradingClientAlpaca
from mt.data.asset import Asset
from mt.data.bars import BarsClientAlpaca
from mt.exchange import TRADING_ZONE, midnight, previous_session_on, today_on
from mt.rules.sections import DashboardSection
from mt.rules.values import UNATTRIBUTED, OrderReason, StrategyKey, Symbol, Unattributed
from mt.sizing import Direction
from mt.strategies.registry import find_order_strategy_key

from .snapshot import Snapshot, SnapshotPosition, build_snapshot, order_reason
from .strategies import STRATEGY_LABELS, StrategyLabel


class FillRow(TypedDict):
    date: str
    minute: int
    price: float
    quantity: float
    side: str
    reason: OrderReason | None


class Attribution(TypedDict):
    strategy_key: StrategyKey | Unattributed
    entered_at: str
    fills: list[FillRow]


class Trade(Attribution):
    symbol: str
    side: str
    quantity: float
    entry: float
    exit: float
    pnl: float
    date: str
    minute: int
    duration_minutes: int


class Totals(TypedDict):
    trade_count: int
    wins: int
    net_pnl: float
    gross_profit: float
    gross_loss: float


class Day(TypedDict):
    date: str
    pnl: float
    trades: int
    wins: int
    before: float | None


class PositionRow(SnapshotPosition):
    strategy_key: StrategyKey | Unattributed
    entered_at: str | None
    fills: list[FillRow]


class EquityDay(TypedDict):
    date: str
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
    isMarketOpen: bool
    nextOpenAt: str
    nextCloseAt: str
    invested: float | None
    strategies: list[StrategyLabel]
    trades: list[Trade]
    days: list[Day]
    totals: Totals
    equityDaily: list[EquityDay]
    benchmarkSymbol: str


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
    order_id: str | None = None


async def build_ledger(
    read: AccountRead,
    trading: TradingClientAlpaca,
    bars_client: BarsClientAlpaca,
    benchmark: Symbol,
    dashboard: DashboardSection,
    daily: list[EquityPoint],
) -> Ledger:
    async with asyncio.TaskGroup() as reads:
        history_read = reads.create_task(trading.history())
        clock_read = reads.create_task(trading.clock())

    account = read.account
    snapshot = build_snapshot(read)
    clock = clock_read.result()
    current_on = today_on()

    history = history_read.result()
    trades, open_trades = _match_trades(history.fills, history.orders, dashboard.flat_quantity_max)
    settled = list(dropwhile(lambda row: not row["equity"], _equity_series(daily, current_on)))
    invested = settled[0]["equity"] if settled else None
    closes = {row["date"]: row["equity"] for row in settled}
    equity_days = [*settled, EquityDay(date=current_on.isoformat(), equity=snapshot["equity"])]

    starts_on = _period_starts(current_on)
    benchmark_bars = await bars_client.series(
        Asset.from_symbol(benchmark),
        "1Day",
        midnight(previous_session_on(min(starts_on.values()))),
        limit=dashboard.bars_max,
        pages_max=dashboard.pages_max,
    )
    benchmark_closes = [
        BenchmarkClose(
            date=bar.opened_at.astimezone(TRADING_ZONE).date().isoformat(), close=bar.close
        )
        for bar in benchmark_bars
    ]
    return {
        **snapshot,
        "periods": {
            key: _period(start_on, equity_days, benchmark_closes)
            for key, start_on in starts_on.items()
        },
        "today": current_on.isoformat(),
        "accountNumber": account.account_number,
        "isMarketOpen": clock.is_open,
        "nextOpenAt": clock.next_open.astimezone(TRADING_ZONE).isoformat(),
        "nextCloseAt": clock.next_close.astimezone(TRADING_ZONE).isoformat(),
        "invested": invested,
        "strategies": STRATEGY_LABELS,
        "positions": _position_rows(snapshot["positions"], open_trades),
        "trades": trades,
        "days": _days(trades, closes, invested),
        "totals": _totals(trades),
        "equityDaily": equity_days,
        "benchmarkSymbol": benchmark,
    }


def _match_trades(
    fills: tuple[Fill, ...],
    orders: tuple[Order, ...],
    flat_quantity_max: float,
) -> tuple[list[Trade], dict[str, Attribution]]:
    strategies: dict[str, StrategyKey | None] = {}
    reasons: dict[str, OrderReason | None] = {}
    for order in orders:
        strategies[str(order.id)] = find_order_strategy_key(order.client_order_id)
        reasons[str(order.id)] = order_reason(order)
    held: defaultdict[str, float] = defaultdict(float)
    tallies: dict[str, _Tally] = {}
    trades: list[Trade] = []

    pending_fills = sorted(fills, key=lambda row: row.transaction_time, reverse=True)
    while pending_fills:
        fill = pending_fills.pop()
        symbol = fill.symbol
        quantity = fill.quantity
        price = fill.price
        when = fill.transaction_time.astimezone(TRADING_ZONE)
        signed = quantity * fill.direction
        current = held[symbol]
        if current * signed < 0 and quantity > abs(current) + flat_quantity_max:
            pending_fills.append(fill.model_copy(update={"quantity": quantity - abs(current)}))
            quantity = abs(current)
            signed = quantity * fill.direction
        held[symbol] += signed

        trade = tallies.get(symbol)
        if trade is None:
            trade = tallies[symbol] = _Tally(
                direction=1 if signed > 0 else -1,
                entered_at=when,
                strategy_key=strategies.get(fill.order_id),
            )

        is_entering = (signed > 0) == (trade.direction > 0)
        side = "in" if is_entering else "out"
        latest = trade.fills[-1] if trade.fills else None
        if latest is not None and trade.order_id == fill.order_id and latest["side"] == side:
            merged = latest["quantity"] + quantity
            trade.fills[-1] = FillRow(
                date=latest["date"],
                minute=latest["minute"],
                price=round((latest["price"] * latest["quantity"] + price * quantity) / merged, 4),
                quantity=round(merged, 4),
                side=latest["side"],
                reason=latest["reason"],
            )
        else:
            trade.fills.append(
                FillRow(
                    date=when.date().isoformat(),
                    minute=_clock_minute(when),
                    price=round(price, 4),
                    quantity=round(quantity, 4),
                    side=side,
                    reason=reasons.get(fill.order_id),
                )
            )
        trade.order_id = fill.order_id
        if is_entering:
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
        symbol: Attribution(
            strategy_key=trade.strategy_key or UNATTRIBUTED,
            entered_at=trade.entered_at.isoformat(),
            fills=trade.fills,
        )
        for symbol, trade in tallies.items()
    }
    return trades, still_open


def _totals(trades: list[Trade]) -> Totals:
    wins = [trade for trade in trades if trade["pnl"] > 0]
    losses = [trade for trade in trades if trade["pnl"] <= 0]
    return Totals(
        trade_count=len(trades),
        wins=len(wins),
        net_pnl=round(sum(trade["pnl"] for trade in trades), 2),
        gross_profit=round(sum(trade["pnl"] for trade in wins), 2),
        gross_loss=round(abs(sum(trade["pnl"] for trade in losses)), 2),
    )


def _days(trades: list[Trade], closes: dict[str, float], opening: float | None) -> list[Day]:
    grouped: defaultdict[str, list[Trade]] = defaultdict(list)
    for trade in trades:
        grouped[trade["date"]].append(trade)

    ordered = sorted(closes)

    def before(day: str) -> float | None:
        index = bisect_left(ordered, day)
        value = closes[ordered[index - 1]] if index else opening
        return None if value is None else round(value, 2)

    return [
        Day(
            date=day,
            pnl=round(sum(trade["pnl"] for trade in grouped[day]), 2),
            trades=len(grouped[day]),
            wins=sum(1 for trade in grouped[day] if trade["pnl"] > 0),
            before=before(day),
        )
        for day in sorted(grouped)
    ]


def _clock_minute(when: datetime) -> int:
    return when.hour * 60 + when.minute


def _period_starts(current_on: date) -> dict[str, date]:
    return {"W": current_on - timedelta(days=current_on.weekday()), "M": current_on.replace(day=1)}


def _period(start_on: date, equity: list[EquityDay], benchmark: list[BenchmarkClose]) -> Period:
    start = start_on.isoformat()
    index = _baseline_index([row["date"] for row in equity], start)
    baseline = _known_baseline(equity[index]["equity"])
    benchmark_baseline = _known_baseline(
        benchmark[_baseline_index([row["date"] for row in benchmark], start)]["close"]
        if benchmark
        else None
    )
    return Period(
        start=start,
        baseline=baseline,
        equityIndex=index,
        benchmarkPct=None
        if benchmark_baseline is None
        else (benchmark[-1]["close"] / benchmark_baseline - 1) * 100,
    )


def _baseline_index(dates: list[str], start: str) -> int:
    return max(0, bisect_left(dates, start) - 1)


def _known_baseline(value: float | None) -> float | None:
    return value or None


def _equity_series(points: list[EquityPoint], before: date) -> list[EquityDay]:
    zoned = [(point.recorded_at.astimezone(TRADING_ZONE), point.equity) for point in points]
    return [
        EquityDay(date=when.date().isoformat(), equity=round(value, 2))
        for when, value in zoned
        if when.date() < before
    ]


def _position_rows(
    raw: Sequence[SnapshotPosition], open_trades: dict[str, Attribution]
) -> list[PositionRow]:
    return [_position_row(position, open_trades.get(position["symbol"])) for position in raw]


def _position_row(position: SnapshotPosition, held: Attribution | None) -> PositionRow:
    if held is None:
        return PositionRow(**position, strategy_key=UNATTRIBUTED, entered_at=None, fills=[])
    return PositionRow(
        **position,
        strategy_key=held["strategy_key"],
        entered_at=held["entered_at"],
        fills=held["fills"],
    )
