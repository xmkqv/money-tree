from datetime import datetime
from pathlib import Path
from typing import cast

from bot.config import settings


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


def _artifact_paths(output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    return {key: str(output_dir / name) for key, name in ARTIFACT_NAMES.items()}


def run(
    strategy_name: str,
    start: datetime,
    end: datetime,
    symbols: list[str] | None = None,
    output_dir: Path | None = None,
) -> dict[str, object]:
    from lumibot.backtesting import AlpacaBacktesting, YahooDataBacktesting

    from bot.strategies.base import load_strategy

    parameters: dict[str, object] = settings.trading_configuration.model_dump()
    if symbols:
        parameters["symbols"] = symbols
    datasource = YahooDataBacktesting
    datasource_configuration: dict[str, str | bool] | None = None
    if strategy_name in {"orb", "orb_momentum"}:
        api_key = settings.alpaca_api_key
        api_secret = settings.alpaca_api_secret
        if api_key is None or api_secret is None:
            raise RuntimeError("Alpaca credentials are required for intraday backtests")
        datasource = AlpacaBacktesting
        datasource_configuration = {
            "API_KEY": api_key.get_secret_value(),
            "API_SECRET": api_secret.get_secret_value(),
            "PAPER": True,
        }
    results = load_strategy(strategy_name).backtest(
        datasource,
        start,
        end,
        config=datasource_configuration,
        parameters=parameters,
        benchmark_asset="SPY",
        budget=100_000.0,
        show_plot=False,
        show_tearsheet=False,
        show_indicators=False,
        show_progress_bar=False,
        save_tearsheet=True,
        save_logfile=output_dir is not None,
        **({} if output_dir is None else _artifact_paths(output_dir)),
    )
    return cast(dict[str, object], results or {})
