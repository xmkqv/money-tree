import os
from datetime import datetime
from pathlib import Path
from typing import cast

from mt.config.settings import settings
from mt.config.values import StrategyKey
from mt.strategies.breakout import Breakout
from mt.strategies.registry import strategy_class

from .broker import broker_credentials


ARTIFACT_NAMES = {
    "stats_file": "stats.csv",
    "trades_file": "trades.csv",
    "settings_file": "settings.json",
    "logfile": "backtest.log",
    "plot_file_html": "plot.html",
    "indicators_file": "indicators.html",
}
LUMIBOT_DISABLE_UI = "LUMIBOT_DISABLE_UI"


def run(
    strategy_key: StrategyKey,
    symbols: list[str],
    start: datetime,
    end: datetime,
    output_dir: Path | None = None,
) -> dict[str, object]:
    from lumibot.backtesting import AlpacaBacktesting, YahooDataBacktesting

    from .portfolio import Portfolio

    parameters: dict[str, object] = {"strategies": [strategy_key], "symbols": symbols}
    datasource = YahooDataBacktesting
    datasource_configuration: dict[str, str | bool] | None = None
    datasource_options: dict[str, object] = {}
    if issubclass(strategy_class(strategy_key), Breakout):
        datasource = AlpacaBacktesting
        datasource_configuration = broker_credentials(paper=True)
        datasource_options = {
            "timestep": "minute",
            "warm_up_trading_days": settings.backtest.warm_up_days,
        }
    report_mode = output_dir is not None
    if report_mode:
        os.environ[LUMIBOT_DISABLE_UI] = "1"
    results = Portfolio.backtest(
        datasource,
        start,
        end,
        config=datasource_configuration,
        parameters=parameters,
        benchmark_asset=settings.benchmark_symbol,
        budget=settings.backtest.budget_usd,
        show_plot=report_mode,
        show_tearsheet=False,
        show_indicators=report_mode,
        show_progress_bar=False,
        save_tearsheet=False,
        save_logfile=report_mode,
        quiet_logs=not report_mode,
        **datasource_options,
        **({} if output_dir is None else _artifact_paths(output_dir)),
    )
    return cast(dict[str, object], results or {})


def report(
    strategy_key: StrategyKey,
    symbols: list[str],
    start: datetime,
    end: datetime,
) -> Path:
    output_dir = Path("runs") / f"{strategy_key}-{start:%Y%m%d}-{end:%Y%m%d}"
    run(strategy_key, symbols, start, end, output_dir=output_dir)
    return output_dir


def _artifact_paths(output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    return {key: str(output_dir / name) for key, name in ARTIFACT_NAMES.items()}
