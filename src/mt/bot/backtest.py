from datetime import datetime
from pathlib import Path

from mt.config.bot import settings as bot_settings
from mt.config.shared import settings
from mt.config.values import StrategyKey
from mt.data.asset import Asset, AssetType
from mt.strategies.breakout import Breakout
from mt.strategies.registry import strategy_class

from .bars import bars_client
from .broker import broker_credentials


ARTIFACT_NAMES = {
    "stats_file": "stats.csv",
    "trades_file": "trades.csv",
    "settings_file": "settings.json",
    "logfile": "backtest.log",
    "plot_file_html": "plot.html",
    "indicators_file": "indicators.html",
}


def report(strategy_key: StrategyKey, assets: list[Asset], start: datetime, end: datetime) -> Path:
    from lumibot.backtesting import AlpacaBacktesting, YahooDataBacktesting

    from .portfolio import Portfolio

    if not assets or any(asset.asset_type != AssetType.STOCK for asset in assets):
        raise ValueError("reports require equity assets")
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
            "warm_up_trading_days": bot_settings.backtest.warm_up_days,
        }
    with bars_client() as bars:
        Portfolio.backtest(
            datasource,
            start,
            end,
            config=datasource_configuration,
            parameters={"strategies": [strategy_key], "assets": assets, "bars": bars},
            benchmark_asset=settings.benchmark_symbol,
            budget=bot_settings.backtest.budget_usd,
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
