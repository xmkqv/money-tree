from datetime import datetime
from pathlib import Path

from pydantic import TypeAdapter

from mt.config.bot import settings
from mt.config.values import StrategyKey, Symbol
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


def report(strategy_key: StrategyKey, symbols: list[str], start: datetime, end: datetime) -> Path:
    if not symbols or len(symbols) != len(set(symbols)):
        raise ValueError("report symbols must be nonempty and distinct")
    symbols = TypeAdapter(list[Symbol]).validate_python(symbols)
    if start.tzinfo != end.tzinfo or end <= start:
        raise ValueError("report end must follow start in the same timezone")

    from lumibot.backtesting import AlpacaBacktesting, YahooDataBacktesting

    from .portfolio import Portfolio

    output_dir = Path("runs") / f"{strategy_key}-{start:%Y%m%d}-{end:%Y%m%d}"
    output_dir.mkdir(parents=True, exist_ok=True)
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
    Portfolio.backtest(
        datasource,
        start,
        end,
        config=datasource_configuration,
        parameters={"strategies": [strategy_key], "symbols": symbols},
        benchmark_asset=settings.benchmark_symbol,
        budget=settings.backtest.budget_usd,
        show_plot=True,
        show_tearsheet=False,
        show_indicators=True,
        show_progress_bar=False,
        save_tearsheet=False,
        save_logfile=True,
        quiet_logs=False,
        **datasource_options,
        **{key: str(output_dir / name) for key, name in ARTIFACT_NAMES.items()},
    )
    return output_dir
