import os
from datetime import datetime
from pathlib import Path
from typing import cast

from .config import settings
from .types import StrategyName


ARTIFACT_NAMES = {
    "stats_file": "stats.csv",
    "trades_file": "trades.csv",
    "settings_file": "settings.json",
    "tearsheet_file": "tearsheet.html",
    "tearsheet_metrics_file": "tearsheet_metrics.json",
    "logfile": "backtest.log",
    "plot_file_html": "plot.html",
    "indicators_file": "indicators.html",
}
LUMIBOT_DISABLE_UI = "LUMIBOT_DISABLE_UI"


def _artifact_paths(output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    return {key: str(output_dir / name) for key, name in ARTIFACT_NAMES.items()}


def run(
    strategy_name: StrategyName,
    start: datetime,
    end: datetime,
    symbols: list[str] | None = None,
    output_dir: Path | None = None,
) -> dict[str, object]:
    from lumibot.backtesting import AlpacaBacktesting, YahooDataBacktesting

    from .portfolio import Strategy

    parameters: dict[str, object] = settings.trading_configuration.model_dump()
    parameters["strategies"] = [strategy_name]
    if symbols:
        parameters["symbols"] = symbols
    datasource = YahooDataBacktesting
    datasource_configuration: dict[str, str | bool] | None = None
    datasource_options: dict[str, object] = {}
    if strategy_name in {"orb", "orb_momentum"}:
        datasource = AlpacaBacktesting
        datasource_configuration = {
            "API_KEY": settings.alpaca_api_key.get_secret_value(),
            "API_SECRET": settings.alpaca_api_secret.get_secret_value(),
            "PAPER": True,
        }
        datasource_options = {"timestep": "minute", "warm_up_trading_days": 60}
    report_mode = output_dir is not None
    previous_disable_ui = os.environ.get(LUMIBOT_DISABLE_UI)
    if report_mode:
        os.environ[LUMIBOT_DISABLE_UI] = "1"
    try:
        results = Strategy.backtest(
            datasource,
            start,
            end,
            config=datasource_configuration,
            parameters=parameters,
            benchmark_asset="SPY",
            budget=100_000.0,
            show_plot=report_mode,
            show_tearsheet=False,
            show_indicators=report_mode,
            show_progress_bar=False,
            save_tearsheet=True,
            save_logfile=report_mode,
            quiet_logs=not report_mode,
            **datasource_options,
            **({} if output_dir is None else _artifact_paths(output_dir)),
        )
    finally:
        if report_mode:
            if previous_disable_ui is None:
                os.environ.pop(LUMIBOT_DISABLE_UI, None)
            else:
                os.environ[LUMIBOT_DISABLE_UI] = previous_disable_ui
    return cast(dict[str, object], results or {})
