from datetime import datetime
from pathlib import Path
from typing import Any, cast

from bot.config import settings


ARTIFACTS = {
    "stats_file": "stats.csv",
    "trades_file": "trades.csv",
    "settings_file": "settings.json",
    "tearsheet_file": "tearsheet.html",
    "tearsheet_metrics_file": "tearsheet_metrics.json",
    "logfile": "backtest.log",
    "plot_file_html": "plot.html",
}


def _files(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    return {key: str(output_dir / name) for key, name in ARTIFACTS.items()}


def run(
    strategy_name: str,
    start: datetime,
    end: datetime,
    symbols: list[str] | None = None,
    output_dir: Path | None = None,
) -> dict[str, object]:
    from lumibot.backtesting import YahooDataBacktesting

    from bot.strategies.shared import load_strategy

    parameters: dict[str, object] = {**settings.risk_parameters}
    if symbols:
        parameters["symbols"] = symbols
    results = load_strategy(strategy_name).backtest(
        YahooDataBacktesting,
        start,
        end,
        parameters=parameters,
        benchmark_asset="SPY",
        budget=100_000.0,
        show_plot=False,
        show_tearsheet=False,
        show_indicators=False,
        show_progress_bar=False,
        save_tearsheet=True,
        **({} if output_dir is None else _files(output_dir)),
    )
    return cast(dict[str, object], results or {})
