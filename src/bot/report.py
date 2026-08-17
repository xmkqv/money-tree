from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from bot._report_analysis import (
    EMPTY_TRADES_MESSAGE,
    LUMIBOT_FALLBACK,
    drawdown_caption,
    equity_caption,
    load_report_data,
    methodology_rows,
    monthly_caption,
    performance_rows,
    summary_text,
    trade_rows,
    trades_caption,
)
from bot._report_render import (
    BulletSection,
    ChartName,
    ImageSection,
    Report,
    Section,
    TableSection,
    markdown,
    render_charts,
)


RUNS_DIR = Path("runs")
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


def _build_report(
    output_dir: Path,
    strategy_name: str,
    symbols: Sequence[str],
    start: datetime,
    end: datetime,
    results: object,
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
    output_dir = RUNS_DIR / f"{strategy_name}-{start:%Y%m%d}-{end:%Y%m%d}"
    output_dir.mkdir(parents=True, exist_ok=True)
    results = run_backtest(strategy_name, start, end, symbols=symbols, output_dir=output_dir)
    report = _build_report(output_dir, display_name, symbols, start, end, results)
    (output_dir / "report.json").write_text(report.model_dump_json(indent=2))
    (output_dir / "report.md").write_text(markdown(report))
    print(output_dir)
    return output_dir
