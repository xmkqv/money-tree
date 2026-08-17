from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal, assert_never, cast

from pydantic import BaseModel, ConfigDict

from bot._report_analysis import (
    EMPTY_TRADES_MESSAGE,
    RoundTrip,
    Series,
    format_money,
    format_percent,
    monthly_returns,
    symbol_totals,
)


type Figure = Any
type Axes = Any
type ChartName = Literal["equity", "drawdown", "monthly", "trades"]

CANVAS = "#061009"
PANEL = "#0f1c13"
LINE = "#21402c"
MUTED = "#8ba694"
INK = "#e1efe5"
ACCENT = "#77e5a2"
WARNING = "#f4c26a"
AREA = "#245f42"
AREA_ALPHA = 0.4
UNDERWATER_ALPHA = 0.5
FIGURE_SIZE = (8.0, 3.5)
FIGURE_DPI = 200
FIGURE_MARGINS = {"left": 0.105, "right": 0.96, "top": 0.86, "bottom": 0.13}
MIN_CHART_ROWS = 4
MONTH_LABELS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
RC_PARAMS: dict[str, object] = {
    "figure.facecolor": CANVAS,
    "figure.edgecolor": CANVAS,
    "savefig.facecolor": CANVAS,
    "savefig.edgecolor": CANVAS,
    "axes.facecolor": PANEL,
    "axes.edgecolor": LINE,
    "axes.linewidth": 0.8,
    "axes.labelcolor": MUTED,
    "axes.titlecolor": INK,
    "axes.titlesize": 13,
    "axes.titleweight": "bold",
    "axes.titlelocation": "left",
    "axes.titlepad": 14,
    "axes.grid": True,
    "axes.grid.axis": "y",
    "axes.axisbelow": True,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "grid.color": LINE,
    "grid.linewidth": 0.6,
    "grid.alpha": 0.8,
    "text.color": INK,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "xtick.labelcolor": MUTED,
    "ytick.labelcolor": MUTED,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "xtick.major.size": 0,
    "ytick.major.size": 0,
    "font.size": 10,
    "legend.frameon": False,
}


class SectionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    heading: str


class TableSection(SectionModel):
    table: list[list[str]]


class ImageSection(SectionModel):
    image: str
    caption: str


class BulletSection(SectionModel):
    bullets: list[str]


type Section = TableSection | ImageSection | BulletSection


class Report(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    title: str
    summary: str
    sections: list[Section]
    footer: str


def _money_tick(value: float, _position: object) -> str:
    return f"${value:,.0f}"


def _percent_tick(value: float, _position: object) -> str:
    return f"{value:.0%}" if abs(value) >= 0.1 or value == 0 else f"{value:.1%}"


def _apply_style() -> None:
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import font_manager, style

    families = {font.name for font in font_manager.fontManager.ttflist}
    preferred = [name for name in ("Inter", "Helvetica Neue", "Arial") if name in families]
    fonts: dict[str, object] = {"font.sans-serif": preferred} if preferred else {}
    style.use(RC_PARAMS | {"font.family": "sans-serif"} | fonts)


def _row_span(count: int) -> tuple[int, float]:
    rows = max(count, MIN_CHART_ROWS)
    return rows, (rows - count) / 2.0


def _readable_ink(face: object) -> str:
    if not isinstance(face, tuple):
        return INK
    channels = cast(tuple[object, ...], face)
    if len(channels) < 3:
        return INK
    red, green, blue = cast(tuple[float, float, float], channels[:3])
    return CANVAS if 0.2126 * red + 0.7152 * green + 0.0722 * blue > 0.5 else INK


def _figure(title: str) -> tuple[Figure, Axes]:
    from matplotlib import pyplot

    plt = cast(Any, pyplot)
    figure, axes = plt.subplots(figsize=FIGURE_SIZE, dpi=FIGURE_DPI)
    figure.subplots_adjust(**FIGURE_MARGINS)
    axes.set_title(title)
    return figure, axes


def _save(figure: Figure, path: Path) -> Path:
    from matplotlib import pyplot

    plt = cast(Any, pyplot)
    figure.savefig(path)
    plt.close(figure)
    return path


def _empty_panel(path: Path, title: str, message: str) -> Path:
    figure, axes = _figure(title)
    axes.grid(False)
    axes.set_xticks([])
    axes.set_yticks([])
    axes.text(
        0.5,
        0.5,
        message,
        transform=axes.transAxes,
        ha="center",
        va="center",
        color=MUTED,
        fontsize=12,
    )
    return _save(figure, path)


def _chart_equity(path: Path, equity: Series) -> Path:
    from matplotlib.ticker import FuncFormatter

    closing = float(equity.iloc[-1])
    figure, axes = _figure(f"Portfolio value — {format_money(closing)} final")
    axes.plot(equity.index, equity.to_numpy(), color=ACCENT, linewidth=1.8)
    axes.fill_between(equity.index, equity.to_numpy(), equity.min(), color=AREA, alpha=AREA_ALPHA)
    axes.yaxis.set_major_formatter(FuncFormatter(_money_tick))
    axes.margins(x=0.01)
    return _save(figure, path)


def _chart_drawdown(path: Path, equity: Series) -> Path:
    from matplotlib.ticker import FuncFormatter

    drawdown = equity / equity.cummax() - 1.0
    figure, axes = _figure("Drawdown from prior peak")
    axes.fill_between(
        drawdown.index, drawdown.to_numpy(), 0.0, color=WARNING, alpha=UNDERWATER_ALPHA
    )
    axes.plot(drawdown.index, drawdown.to_numpy(), color=WARNING, linewidth=1.2)
    axes.yaxis.set_major_formatter(FuncFormatter(_percent_tick))
    axes.margins(x=0.01)
    trough = float(drawdown.min())
    if trough < 0:
        axes.annotate(
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
    from matplotlib.patches import Rectangle

    monthly = monthly_returns(returns)
    if not monthly:
        return _empty_panel(path, "Monthly returns", "No monthly history in window")
    years = sorted({year for year, _ in monthly})
    scale = max((abs(value) for value in monthly.values()), default=0.0) or 0.01
    colors = LinearSegmentedColormap.from_list("money-tree", [WARNING, PANEL, ACCENT])
    norm = Normalize(vmin=-scale, vmax=scale)
    rows, offset = _row_span(len(years))
    figure, axes = _figure("Monthly returns")
    axes.grid(False)
    axes.set_facecolor(CANVAS)
    for index, year in enumerate(years):
        row = index + offset
        for column in range(12):
            value = monthly.get((year, column + 1))
            face = PANEL if value is None else colors(norm(value))
            axes.add_patch(
                Rectangle(
                    (column - 0.5, row - 0.5),
                    1.0,
                    1.0,
                    facecolor=face,
                    edgecolor=CANVAS,
                    linewidth=1.5,
                )
            )
            if value is not None:
                axes.text(
                    column,
                    row,
                    f"{value * 100:.1f}%",
                    ha="center",
                    va="center",
                    color=_readable_ink(face),
                    fontsize=9,
                )
    axes.set_xlim(-0.5, 11.5)
    axes.set_ylim(rows - 0.5, -0.5)
    axes.set_xticks(range(12), MONTH_LABELS)
    axes.set_yticks([index + offset for index in range(len(years))], [str(y) for y in years])
    for side in ("left", "bottom"):
        axes.spines[side].set_visible(False)
    return _save(figure, path)


def _chart_trades(path: Path, trips: Sequence[RoundTrip]) -> Path:
    if not trips:
        return _empty_panel(path, "Realized P&L by symbol", EMPTY_TRADES_MESSAGE)
    from matplotlib.ticker import FuncFormatter

    totals = sorted(symbol_totals(trips).items(), key=lambda item: item[1])
    labels = [symbol for symbol, _ in totals]
    values = [value for _, value in totals]
    rows, offset = _row_span(len(values))
    positions = [index + offset for index in range(len(values))]
    figure, axes = _figure("Realized P&L by symbol")
    axes.grid(False, axis="y")
    axes.grid(True, axis="x")
    axes.barh(
        positions,
        values,
        height=0.55,
        color=[ACCENT if value >= 0 else WARNING for value in values],
    )
    axes.axvline(0.0, color=LINE, linewidth=1.0)
    axes.xaxis.set_major_formatter(FuncFormatter(_money_tick))
    axes.set_yticks(positions, labels)
    axes.set_ylim(-0.5, rows - 0.5)
    span = max((abs(value) for value in values), default=1.0) or 1.0
    for row, value in zip(positions, values, strict=True):
        gap = span * 0.02
        axes.text(
            value + (gap if value >= 0 else -gap),
            row,
            format_money(value),
            va="center",
            ha="left" if value >= 0 else "right",
            color=ACCENT if value >= 0 else WARNING,
            fontsize=9,
        )
    axes.margins(x=0.12)
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
