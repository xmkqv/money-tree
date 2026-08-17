from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, assert_never, cast

from matplotlib.axes import Axes
from matplotlib.figure import Figure
from pandas import Series

from bot._report_analysis import (
    EMPTY_TRADES_MESSAGE,
    LUMIBOT_FALLBACK,
    drawdown_caption,
    equity_caption,
    format_money,
    format_percent,
    load_report_data,
    methodology_rows,
    monthly_caption,
    monthly_returns,
    performance_rows,
    summary_text,
    symbol_totals,
    trade_rows,
    trades_caption,
)
from bot.types import (
    BulletSection,
    ChartName,
    ImageSection,
    Report,
    RoundTrip,
    Section,
    TableSection,
)


PANEL = "#0f1c13"
ACCENT = "#77e5a2"
WARNING = "#f4c26a"
MONTH_LABELS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
PANELS: tuple[tuple[ChartName, str], ...] = (
    ("equity", "Equity curve"),
    ("drawdown", "Drawdown"),
    ("monthly", "Monthly returns"),
    ("trades", "Trade attribution"),
)
LIMITATIONS = (
    "The universe is fixed in advance, so the result carries survivorship and selection bias.",
    "No commissions, spreads, borrow costs, or slippage are modeled; live fills will be worse.",
    "A single backtest window carries no out-of-sample validation, so overfitting stays possible.",
    "Daily bars hide intraday drawdown, gap risk, and the true path of every position.",
    "Yahoo adjusted history is revised over time, so the same window can shift between runs.",
)


def _money_tick(value: float, _position: object) -> str:
    return f"${value:,.0f}"


def _percent_tick(value: float, _position: object) -> str:
    return f"{value:.0%}" if abs(value) >= 0.1 or value == 0 else f"{value:.1%}"


def _apply_style() -> None:
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import style

    style.use("dark_background")


def _figure(title: str) -> tuple[Figure, Axes]:
    from matplotlib import pyplot

    figure, axes = cast(
        tuple[Figure, Axes], cast(Any, pyplot).subplots(figsize=(8.0, 3.5), dpi=200)
    )
    cast(Any, axes).set_title(title)
    return figure, axes


def _save(figure: Figure, path: Path) -> Path:
    from matplotlib import pyplot

    cast(Any, figure).savefig(path)
    cast(Any, pyplot).close(figure)
    return path


def _empty_panel(path: Path, title: str, message: str) -> Path:
    figure, axes = _figure(title)
    panel = cast(Any, axes)
    panel.grid(False)
    panel.set_xticks([])
    panel.set_yticks([])
    panel.text(
        0.5,
        0.5,
        message,
        transform=panel.transAxes,
        ha="center",
        va="center",
        color="#8ba694",
        fontsize=12,
    )
    return _save(figure, path)


def _chart_equity(path: Path, equity: Series) -> Path:
    from matplotlib.ticker import FuncFormatter

    values = cast(Any, equity)
    closing = float(values.iloc[-1])
    figure, axes = _figure(f"Portfolio value — {format_money(closing)} final")
    panel = cast(Any, axes)
    panel.plot(values.index, values.to_numpy(), color=ACCENT, linewidth=1.8)
    panel.fill_between(values.index, values.to_numpy(), values.min(), color=ACCENT, alpha=0.25)
    panel.yaxis.set_major_formatter(FuncFormatter(_money_tick))
    panel.margins(x=0.01)
    return _save(figure, path)


def _chart_drawdown(path: Path, equity: Series) -> Path:
    from matplotlib.ticker import FuncFormatter

    values = cast(Any, equity)
    drawdown = values / values.cummax() - 1.0
    figure, axes = _figure("Drawdown from prior peak")
    panel = cast(Any, axes)
    panel.fill_between(drawdown.index, drawdown.to_numpy(), 0.0, color=WARNING, alpha=0.5)
    panel.plot(drawdown.index, drawdown.to_numpy(), color=WARNING, linewidth=1.2)
    panel.yaxis.set_major_formatter(FuncFormatter(_percent_tick))
    panel.margins(x=0.01)
    trough = float(drawdown.min())
    if trough < 0:
        panel.annotate(
            format_percent(trough),
            xy=(drawdown.idxmin(), trough),
            xytext=(8, 6),
            textcoords="offset points",
            ha="left",
            va="bottom",
            color=WARNING,
            fontsize=11,
            fontweight="bold",
        )
    return _save(figure, path)


def _chart_monthly(path: Path, returns: Series) -> Path:
    from matplotlib.colors import LinearSegmentedColormap, Normalize

    monthly = monthly_returns(returns)
    if not monthly:
        return _empty_panel(path, "Monthly returns", "No monthly history in window")
    years = sorted({year for year, _ in monthly})
    scale = max((abs(value) for value in monthly.values()), default=0.0) or 0.01
    colors = LinearSegmentedColormap.from_list("money-tree", [WARNING, PANEL, ACCENT])
    norm = Normalize(vmin=-scale, vmax=scale)
    figure, axes = _figure("Monthly returns")
    panel = cast(Any, axes)
    grid = [[monthly.get((year, month), float("nan")) for month in range(1, 13)] for year in years]
    panel.imshow(grid, cmap=colors, norm=norm, aspect="auto")
    for row, values in enumerate(grid):
        for column, value in enumerate(values):
            if value == value:
                panel.text(column, row, f"{value:.1%}", ha="center", va="center", fontsize=9)
    panel.set_xticks(range(12), MONTH_LABELS)
    panel.set_yticks(range(len(years)), [str(year) for year in years])
    return _save(figure, path)


def _chart_trades(path: Path, trips: Sequence[RoundTrip]) -> Path:
    if not trips:
        return _empty_panel(path, "Realized P&L by symbol", EMPTY_TRADES_MESSAGE)
    from matplotlib.ticker import FuncFormatter

    totals = sorted(symbol_totals(trips).items(), key=lambda item: item[1])
    labels = [symbol for symbol, _ in totals]
    values = [value for _, value in totals]
    figure, axes = _figure("Realized P&L by symbol")
    panel = cast(Any, axes)
    panel.barh(
        labels,
        values,
        color=[ACCENT if value >= 0 else WARNING for value in values],
    )
    panel.axvline(0.0, color="#21402c", linewidth=1.0)
    panel.xaxis.set_major_formatter(FuncFormatter(_money_tick))
    panel.margins(x=0.12)
    return _save(figure, path)


def render_charts(
    output_dir: Path, equity: Series, returns: Series, trips: Sequence[RoundTrip]
) -> dict[ChartName, Path]:
    _apply_style()
    return {
        "equity": _chart_equity(output_dir / "equity.png", equity),
        "drawdown": _chart_drawdown(output_dir / "drawdown.png", equity),
        "monthly": _chart_monthly(output_dir / "monthly.png", returns),
        "trades": _chart_trades(output_dir / "trades.png", trips),
    }


def _markdown_row(cells: Sequence[str]) -> str:
    return f"| {' | '.join(cells)} |"


def _markdown_body(section: Section) -> list[str]:
    match section:
        case TableSection():
            header, *rest = section.table
            return [
                _markdown_row(header),
                _markdown_row(["---"] * len(header)),
                *(_markdown_row(row) for row in rest),
            ]
        case ImageSection():
            return [f"![{section.caption}]({section.image})"]
        case BulletSection():
            return [f"- {item}" for item in section.bullets]
    assert_never(section)


def markdown(report: Report) -> str:
    lines = [f"# {report.title}", "", f"> {report.summary}"]
    for section in report.sections:
        lines.extend(["", f"## {section.heading}", "", *_markdown_body(section)])
    lines.extend(["", report.footer, ""])
    return "\n".join(lines)


def _build_report(
    output_dir: Path,
    strategy_name: str,
    symbols: Sequence[str],
    start: datetime,
    end: datetime,
    results: Mapping[str, object],
) -> Report:
    data = load_report_data(output_dir, results)
    charts = render_charts(output_dir, data.equity, data.returns, data.trips)
    captions = {
        "equity": equity_caption(data.equity),
        "drawdown": drawdown_caption(data.equity),
        "monthly": monthly_caption(data.returns),
        "trades": trades_caption(data.trips),
    }
    sections: list[Section] = [
        TableSection(heading="Performance", table=performance_rows(data)),
        *(
            ImageSection(heading=heading, image=charts[name].name, caption=captions[name])
            for name, heading in PANELS
        ),
        TableSection(
            heading="Methodology",
            table=methodology_rows(symbols, start, end, data.settings),
        ),
    ]
    rows = trade_rows(data.trips)
    header = ["Symbol", "Entry date", "Exit date", "Days", "P&L $", "Return %"]
    sections.append(
        TableSection(heading="Trades", table=[header, *rows])
        if rows
        else BulletSection(heading="Trades", bullets=[EMPTY_TRADES_MESSAGE])
    )
    sections.append(BulletSection(heading="Limitations", bullets=list(LIMITATIONS)))
    version = data.settings.lumibot_version or LUMIBOT_FALLBACK
    return Report(
        title=f"Backtest — {strategy_name} — {start:%Y-%m-%d} → {end:%Y-%m-%d}",
        summary=summary_text(strategy_name, symbols, start, end, data),
        sections=sections,
        footer=(
            f"Generated {datetime.now(UTC):%Y-%m-%d %H:%M UTC} · money-tree · "
            f"Lumibot {version} · run {output_dir.name}"
        ),
    )


def run(
    strategy_name: str,
    symbols: list[str],
    start: datetime,
    end: datetime,
    label: str | None = None,
) -> Path:
    from bot.backtest import run as run_backtest

    display_name = label or strategy_name
    output_dir = Path("runs") / f"{strategy_name}-{start:%Y%m%d}-{end:%Y%m%d}"
    output_dir.mkdir(parents=True, exist_ok=True)
    results = run_backtest(strategy_name, start, end, symbols=symbols, output_dir=output_dir)
    report = _build_report(output_dir, display_name, symbols, start, end, results)
    (output_dir / "report.json").write_text(report.model_dump_json(indent=2))
    (output_dir / "report.md").write_text(markdown(report))
    print(output_dir)
    return output_dir
