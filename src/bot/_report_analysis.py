import json
from collections import defaultdict, deque
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import replace
from datetime import datetime
from numbers import Real
from pathlib import Path
from typing import Any, cast

import pandas
from pandas import DataFrame, Series

from bot.types import Fill, ReportData, ReportRow, RoundTrip, RunSettings, TradeStats


TRADING_ZONE = "America/New_York"
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


SCALAR_ROWS: tuple[tuple[str, str, Callable[[float], str], str], ...] = (
    ("Sortino", "Sortino", _format_ratio, "Strategy"),
    ("Calmar", "Calmar", _format_ratio, "Strategy"),
    ("Time in Market", "Time in market", format_percent, "Strategy"),
    ("Total Return", "Benchmark total return", format_percent, "Benchmark"),
    ("Sharpe", "Benchmark Sharpe", _format_ratio, "Benchmark"),
    ("Corr to Benchmark", "Correlation to benchmark", _format_ratio, "Strategy"),
    ("Longest DD Days", "Longest drawdown (days)", _format_count, "Strategy"),
)


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, Real):
        return None
    number = float(value)
    return number if number == number and abs(number) != float("inf") else None


def _leg(value: object, leg: str) -> object:
    return cast(Mapping[str, object], value).get(leg) if isinstance(value, Mapping) else value


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


def _load_history(output_dir: Path) -> tuple[Series, Series]:
    pd = cast(Any, pandas)
    frame: DataFrame = pd.read_csv(
        output_dir / "stats.csv", usecols=["datetime", "portfolio_value", "return"]
    )
    values = cast(Any, frame)
    stamps = pd.to_datetime(values["datetime"], utc=True).dt.tz_convert(TRADING_ZONE)
    equity = cast(
        Series, pd.Series(values["portfolio_value"].astype(float).to_numpy(), index=stamps)
    )
    returns = cast(Series, pd.Series(values["return"].astype(float).to_numpy(), index=stamps))
    return cast(Series, cast(Any, equity).resample("D").last().dropna()), cast(
        Series, cast(Any, returns).dropna()
    )


def _load_round_trips(output_dir: Path) -> list[RoundTrip]:
    path = output_dir / "trades.csv"
    if not path.exists():
        return []
    pd = cast(Any, pandas)
    frame: DataFrame = pd.read_csv(path)
    if frame.empty:
        return []
    fills: list[Fill] = []
    records = cast(list[dict[str, object]], cast(Any, frame).to_dict("records"))
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


def load_report_data(output_dir: Path, results: Mapping[str, object]) -> ReportData:
    equity, returns = _load_history(output_dir)
    trips = _load_round_trips(output_dir)
    return ReportData(
        equity=equity,
        returns=returns,
        trips=trips,
        settings=_load_settings(output_dir),
        analytics=results,
        trades=_trade_stats(trips),
        scalars=_load_scalars(output_dir),
    )


def performance_rows(data: ReportData) -> list[ReportRow]:
    rows: list[ReportRow] = [["Metric", "Value"]]

    def add(label: str, value: float | None, formatter: Callable[[float], str]) -> None:
        if value is not None:
            rows.append([label, formatter(value)])

    analytics = data.analytics
    trades = data.trades
    add("Total return", _number(analytics.get("total_return")), format_percent)
    add("CAGR", _number(analytics.get("cagr")), format_percent)
    add("Volatility (ann.)", _number(analytics.get("volatility")), format_percent)
    add("Sharpe", _number(analytics.get("sharpe")), _format_ratio)
    max_drawdown = _number(_leg(analytics.get("max_drawdown"), "drawdown"))
    if max_drawdown is not None:
        depth = format_percent(-abs(max_drawdown))
        drawdown_at = _leg(analytics.get("max_drawdown"), "date")
        on_date = drawdown_at.date().isoformat() if isinstance(drawdown_at, datetime) else None
        rows.append(["Max drawdown", f"{depth} on {on_date}" if on_date else depth])
    add("Return over max drawdown", _number(analytics.get("romad")), _format_ratio)
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
) -> list[ReportRow]:
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


def trade_rows(trips: Sequence[RoundTrip]) -> list[ReportRow]:
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
    analytics = data.analytics
    total_return = _number(analytics.get("total_return"))
    total = format_percent(total_return) if total_return is not None else "flat"
    window = f"{start:%b %Y} to {end:%b %Y}"
    first = f"The {strategy_name} strategy returned {total} across {universe} from {window}"
    cagr = _number(analytics.get("cagr"))
    if cagr is not None:
        first = f"{first}, compounding at {format_percent(cagr)} a year"
    parts: list[str] = []
    max_drawdown = _number(_leg(analytics.get("max_drawdown"), "drawdown"))
    if max_drawdown is not None:
        depth = format_percent(-abs(max_drawdown))
        drawdown_at = _leg(analytics.get("max_drawdown"), "date")
        on_date = drawdown_at.date().isoformat() if isinstance(drawdown_at, datetime) else None
        parts.append(f"the deepest drawdown was {depth}{f' on {on_date}' if on_date else ''}")
    sharpe = _number(analytics.get("sharpe"))
    if sharpe is not None:
        parts.append(f"the Sharpe ratio came in at {_format_ratio(sharpe)}")
    if data.trades.count and data.trades.win_rate is not None:
        parts.append(
            f"{data.trades.count} round-trip trades closed at a "
            f"{format_percent(data.trades.win_rate)} win rate"
        )
    elif not data.trades.count:
        parts.append("no position was opened and closed inside the window")
    return f"{first}. On the risk side, {_series_text(parts)}."


def equity_caption(equity: Series) -> str:
    values = cast(Any, equity)
    opening = float(values.iloc[0])
    closing = float(values.iloc[-1])
    direction = "up" if closing >= opening else "down"
    return (
        f"Portfolio value closed the window at {format_money(closing)}, {direction} "
        f"from {format_money(opening)} at the first recorded bar."
    )


def drawdown_caption(equity: Series) -> str:
    values = cast(Any, equity)
    drawdown = values / values.cummax() - 1.0
    return (
        f"The worst drawdown reached {format_percent(float(drawdown.min()))}, and "
        f"{int((drawdown < 0).sum())} of {len(drawdown)} days closed below a prior peak."
    )


def monthly_returns(returns: Series) -> dict[tuple[int, int], float]:
    if returns.empty:
        return {}
    compounded = (1.0 + cast(Any, returns)).resample("ME").prod() - 1.0
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
