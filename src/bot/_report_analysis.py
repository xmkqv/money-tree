import json
from collections import defaultdict, deque
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from numbers import Real
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field


type Series = Any
type Row = list[str]
type Formatter = Callable[[float], str]

TRADING_ZONE = "America/New_York"
SECONDS_PER_DAY = 86400.0
LUMIBOT_FALLBACK = "4.5.83"
TRADE_ROW_MAX = 10
EMPTY_TRADES_MESSAGE = "No round-trip trades in window"


def format_money(value: float) -> str:
    return f"-${abs(value):,.0f}" if value < 0 else f"${value:,.0f}"


def format_percent(value: float) -> str:
    return f"{value * 100 or 0.0:.1f}%"


def _format_ratio(value: float) -> str:
    return f"{value:.2f}"


def _format_count(value: float) -> str:
    return f"{value:,.0f}"


SCALAR_ROWS: tuple[tuple[str, str, Formatter, str], ...] = (
    ("Sortino", "Sortino", _format_ratio, "Strategy"),
    ("Calmar", "Calmar", _format_ratio, "Strategy"),
    ("Time in Market", "Time in market", format_percent, "Strategy"),
    ("Total Return", "Benchmark total return", format_percent, "Benchmark"),
    ("Sharpe", "Benchmark Sharpe", _format_ratio, "Benchmark"),
    ("Corr to Benchmark", "Correlation to benchmark", _format_ratio, "Strategy"),
    ("Longest DD Days", "Longest drawdown (days)", _format_count, "Strategy"),
)


class RunSettings(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    budget: float | None = None
    benchmark_asset: str | dict[str, object] | None = None
    lumibot_version: str | None = None
    parameters: dict[str, object] = Field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Fill:
    symbol: str
    sign: int
    quantity: float
    price: float
    filled_at: datetime


@dataclass(frozen=True, slots=True)
class RoundTrip:
    symbol: str
    sign: int
    quantity: float
    entry_at: datetime
    exit_at: datetime
    entry_price: float
    exit_price: float

    @property
    def pnl_usd(self) -> float:
        return self.sign * (self.exit_price - self.entry_price) * self.quantity

    @property
    def return_fraction(self) -> float:
        return self.sign * (self.exit_price / self.entry_price - 1.0)

    @property
    def holding_days(self) -> float:
        return (self.exit_at - self.entry_at).total_seconds() / SECONDS_PER_DAY


@dataclass(frozen=True, slots=True)
class Performance:
    total_return: float | None
    cagr: float | None
    volatility: float | None
    sharpe: float | None
    max_drawdown: float | None
    max_drawdown_on: str | None
    romad: float | None


@dataclass(frozen=True, slots=True)
class TradeStats:
    count: int
    win_rate: float | None
    profit_factor: float | None
    average_win: float | None
    average_loss: float | None
    best: float | None
    worst: float | None
    average_days: float | None


@dataclass(frozen=True, slots=True)
class ReportData:
    equity: Series
    returns: Series
    trips: list[RoundTrip]
    settings: RunSettings
    performance: Performance
    trades: TradeStats
    scalars: dict[str, object]


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, Real):
        return None
    number = float(value)
    return number if number == number and abs(number) != float("inf") else None


def _leg(value: object, leg: str) -> object:
    return cast(dict[str, object], value).get(leg) if isinstance(value, dict) else value


def _load_settings(output_dir: Path) -> RunSettings:
    path = output_dir / "settings.json"
    return RunSettings.model_validate_json(path.read_bytes()) if path.exists() else RunSettings()


def _load_scalars(output_dir: Path) -> dict[str, object]:
    path = output_dir / "tearsheet_metrics.json"
    if not path.exists():
        return {}
    loaded = json.loads(path.read_bytes())
    if not isinstance(loaded, dict):
        return {}
    document = cast(dict[str, object], loaded)
    metadata = document.get("metadata")
    if (
        isinstance(metadata, dict)
        and cast(dict[str, object], metadata).get("status") == "unavailable"
    ):
        return {}
    scalars = document.get("scalar_metrics")
    return cast(dict[str, object], scalars) if isinstance(scalars, dict) else {}


def _load_equity(output_dir: Path) -> Series:
    import pandas

    pd = cast(Any, pandas)
    frame = pd.read_csv(output_dir / "stats.csv")
    stamps = pd.to_datetime(frame["datetime"], utc=True).dt.tz_convert(TRADING_ZONE)
    series = pd.Series(frame["portfolio_value"].astype(float).to_numpy(), index=stamps)
    return series.resample("D").last().dropna()


def _load_round_trips(output_dir: Path) -> list[RoundTrip]:
    import pandas

    pd = cast(Any, pandas)
    path = output_dir / "trades.csv"
    if not path.exists():
        return []
    frame = pd.read_csv(path)
    if frame.empty:
        return []
    fills: list[Fill] = []
    records = cast(list[dict[str, object]], frame.to_dict("records"))
    for record in records:
        symbol = record.get("symbol")
        side = record.get("side")
        quantity = _number(record.get("filled_quantity"))
        price = _number(record.get("price"))
        filled_at = record.get("time")
        filled_at = datetime.fromisoformat(filled_at) if isinstance(filled_at, str) else None
        if record.get("status") != "fill" or filled_at is None:
            continue
        if quantity is None or price is None or quantity <= 0 or price <= 0:
            continue
        if not isinstance(symbol, str) or side not in ("buy", "sell"):
            continue
        fills.append(Fill(symbol, 1 if side == "buy" else -1, quantity, price, filled_at))
    fills.sort(key=lambda fill: fill.filled_at)
    return _pair_fills(fills)


def _pair_fills(fills: Iterable[Fill]) -> list[RoundTrip]:
    open_lots: dict[str, deque[Fill]] = defaultdict(deque)
    trips: list[RoundTrip] = []
    for fill in fills:
        lots = open_lots[fill.symbol]
        remaining = fill.quantity
        while remaining > 0 and lots and lots[0].sign != fill.sign:
            lot = lots[0]
            matched = min(lot.quantity, remaining)
            trips.append(
                RoundTrip(
                    fill.symbol,
                    lot.sign,
                    matched,
                    lot.filled_at,
                    fill.filled_at,
                    lot.price,
                    fill.price,
                )
            )
            remaining -= matched
            if lot.quantity > matched:
                lots[0] = replace(lot, quantity=lot.quantity - matched)
            else:
                lots.popleft()
        if remaining > 0:
            lots.append(replace(fill, quantity=remaining))
    return trips


def _performance(results: object) -> Performance:
    values = cast(dict[str, object], results) if isinstance(results, dict) else {}
    drawdown = _leg(values.get("max_drawdown"), "drawdown")
    depth = _number(drawdown)
    drawdown_at = _leg(values.get("max_drawdown"), "date")
    return Performance(
        total_return=_number(values.get("total_return")),
        cagr=_number(values.get("cagr")),
        volatility=_number(values.get("volatility")),
        sharpe=_number(values.get("sharpe")),
        max_drawdown=None if depth is None else -abs(depth),
        max_drawdown_on=drawdown_at.date().isoformat()
        if isinstance(drawdown_at, datetime)
        else None,
        romad=_number(values.get("romad")),
    )


def _trade_stats(trips: Sequence[RoundTrip]) -> TradeStats:
    if not trips:
        return TradeStats(0, None, None, None, None, None, None, None)
    profits = [trip.pnl_usd for trip in trips]
    wins = [value for value in profits if value > 0]
    losses = [value for value in profits if value < 0]
    return TradeStats(
        count=len(trips),
        win_rate=len(wins) / len(profits),
        profit_factor=sum(wins) / abs(sum(losses)) if losses else None,
        average_win=sum(wins) / len(wins) if wins else None,
        average_loss=sum(losses) / len(losses) if losses else None,
        best=max(profits),
        worst=min(profits),
        average_days=sum(trip.holding_days for trip in trips) / len(trips),
    )


def load_report_data(output_dir: Path, results: object) -> ReportData:
    equity = _load_equity(output_dir)
    trips = _load_round_trips(output_dir)
    return ReportData(
        equity=equity,
        returns=equity.pct_change().dropna(),
        trips=trips,
        settings=_load_settings(output_dir),
        performance=_performance(results),
        trades=_trade_stats(trips),
        scalars=_load_scalars(output_dir),
    )


def performance_rows(data: ReportData) -> list[Row]:
    rows: list[Row] = [["Metric", "Value"]]

    def add(label: str, value: float | None, formatter: Formatter) -> None:
        if value is not None:
            rows.append([label, formatter(value)])

    performance = data.performance
    trades = data.trades
    add("Total return", performance.total_return, format_percent)
    add("CAGR", performance.cagr, format_percent)
    add("Volatility (ann.)", performance.volatility, format_percent)
    add("Sharpe", performance.sharpe, _format_ratio)
    if performance.max_drawdown is not None:
        depth = format_percent(performance.max_drawdown)
        on_date = performance.max_drawdown_on
        rows.append(["Max drawdown", f"{depth} on {on_date}" if on_date else depth])
    add("Return over max drawdown", performance.romad, _format_ratio)
    for key, label, formatter, leg in SCALAR_ROWS:
        add(label, _number(_leg(data.scalars.get(key), leg)), formatter)
    rows.append(["Round-trip trades", _format_count(trades.count)])
    add("Win rate", trades.win_rate, format_percent)
    add("Profit factor", trades.profit_factor, _format_ratio)
    add("Average win", trades.average_win, format_money)
    add("Average loss", trades.average_loss, format_money)
    add("Best trade", trades.best, format_money)
    add("Worst trade", trades.worst, format_money)
    add("Average holding period (days)", trades.average_days, lambda value: f"{value:,.1f}")
    return rows


def methodology_rows(
    symbols: Sequence[str], start: datetime, end: datetime, settings: RunSettings
) -> list[Row]:
    version = settings.lumibot_version or LUMIBOT_FALLBACK
    risk = _number(settings.parameters.get("risk_per_trade_max"))
    sizing = f"{format_percent(risk)} of equity risked per trade" if risk else "strategy-defined"
    benchmark = settings.benchmark_asset
    return [
        ["Item", "Detail"],
        ["Engine", f"Lumibot {version} (event-driven)"],
        ["Data", "Yahoo Finance daily OHLCV, split/dividend adjusted"],
        ["Universe", ", ".join(symbols)],
        ["Window", f"{start:%Y-%m-%d} → {end:%Y-%m-%d}"],
        ["Starting capital", format_money(settings.budget) if settings.budget else "unstated"],
        ["Benchmark", benchmark if isinstance(benchmark, str) else "SPY"],
        ["Fills", "Next-bar market fills, no commissions or slippage modeled"],
        ["Position sizing", sizing],
    ]


def trade_rows(trips: Sequence[RoundTrip]) -> list[Row]:
    ranked = sorted(trips, key=lambda trip: abs(trip.pnl_usd), reverse=True)[:TRADE_ROW_MAX]
    return [
        [
            trip.symbol,
            trip.entry_at.date().isoformat(),
            trip.exit_at.date().isoformat(),
            f"{trip.holding_days:.0f}",
            format_money(trip.pnl_usd),
            format_percent(trip.return_fraction),
        ]
        for trip in ranked
    ]


def _series_text(parts: Sequence[str]) -> str:
    if len(parts) < 3:
        return " and ".join(parts)
    return f"{', '.join(parts[:-1])}, and {parts[-1]}"


def summary_text(
    strategy_name: str,
    symbols: Sequence[str],
    start: datetime,
    end: datetime,
    data: ReportData,
) -> str:
    instrument_count = len(symbols)
    universe = f"{instrument_count} instrument{'' if instrument_count == 1 else 's'}"
    performance = data.performance
    total = (
        format_percent(performance.total_return) if performance.total_return is not None else "flat"
    )
    window = f"{start:%b %Y} to {end:%b %Y}"
    first = f"The {strategy_name} strategy returned {total} across {universe} from {window}"
    if performance.cagr is not None:
        first = f"{first}, compounding at {format_percent(performance.cagr)} a year"
    parts: list[str] = []
    if performance.max_drawdown is not None:
        depth = format_percent(performance.max_drawdown)
        on_date = performance.max_drawdown_on
        parts.append(f"the deepest drawdown was {depth}{f' on {on_date}' if on_date else ''}")
    if performance.sharpe is not None:
        parts.append(f"the Sharpe ratio came in at {_format_ratio(performance.sharpe)}")
    if data.trades.count and data.trades.win_rate is not None:
        parts.append(
            f"{data.trades.count} round-trip trades closed at a "
            f"{format_percent(data.trades.win_rate)} win rate"
        )
    elif not data.trades.count:
        parts.append("no position was opened and closed inside the window")
    return f"{first}. On the risk side, {_series_text(parts)}."


def equity_caption(equity: Series) -> str:
    opening = float(equity.iloc[0])
    closing = float(equity.iloc[-1])
    direction = "up" if closing >= opening else "down"
    return (
        f"Portfolio value closed the window at {format_money(closing)}, {direction} "
        f"from {format_money(opening)} at the first recorded bar."
    )


def drawdown_caption(equity: Series) -> str:
    drawdown = equity / equity.cummax() - 1.0
    return (
        f"The worst drawdown reached {format_percent(float(drawdown.min()))}, and "
        f"{int((drawdown < 0).sum())} of {len(drawdown)} days closed below a prior peak."
    )


def monthly_returns(returns: Series) -> dict[tuple[int, int], float]:
    if returns.empty:
        return {}
    compounded = (1.0 + returns).resample("ME").prod() - 1.0
    return {(stamp.year, stamp.month): float(value) for stamp, value in compounded.items()}


def monthly_caption(returns: Series) -> str:
    monthly = monthly_returns(returns)
    if not monthly:
        return "Not enough history to break the return down by month."
    values = list(monthly.values())
    wins = sum(1 for value in values if value > 0)
    return (
        f"{wins} of {len(values)} months finished positive, with a best month of "
        f"{format_percent(max(values))} and a worst month of {format_percent(min(values))}."
    )


def symbol_totals(trips: Sequence[RoundTrip]) -> dict[str, float]:
    totals: dict[str, float] = defaultdict(float)
    for trip in trips:
        totals[trip.symbol] += trip.pnl_usd
    return dict(totals)


def trades_caption(trips: Sequence[RoundTrip]) -> str:
    if not trips:
        return "No position was opened and closed in the window, so there is nothing to attribute."
    totals = symbol_totals(trips)
    leader, contribution = max(totals.items(), key=lambda item: item[1])
    return (
        f"{len(trips)} round trips across {len(totals)} symbols; "
        f"{leader} contributed the most at {format_money(contribution)}."
    )
