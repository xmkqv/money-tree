import signal

from mt.config.settings import RuleSettings
from mt.config.shared import settings
from mt.config.values import StrategyKey
from mt.strategies.registry import strategy_class

from .bars import bars_client
from .broker import alpaca_broker
from .export import StateExporter


def trade(strategies: list[StrategyKey]) -> None:
    from lumibot.traders import Trader

    from .portfolio import Portfolio

    paused: list[StrategyKey] = [key for key in strategies if strategy_class(key).is_paused]
    exporter = StateExporter(
        strategies,
        paused,
        RuleSettings.model_validate(settings.model_dump()),
    )
    exporter.start()
    exporter.publish("starting", "run.started", "info", "Trading run is starting")
    try:
        with bars_client() as bars:
            parameters: dict[str, object] = {"strategies": strategies, "bars": bars}
            strategy = Portfolio(broker=alpaca_broker(), parameters=parameters, name="Portfolio")
            strategy.exporter = exporter
            trader = Trader()
            trader.add_strategy(strategy)
            signal.signal(signal.SIGTERM, lambda number, frame: trader.stop_all())
            exporter.publish("running", "run.activated", "info", "Trading run is active")
            try:
                trader.run_all()
            finally:
                trader.stop_all()
                if strategy._executor.ident is not None:
                    strategy._executor.join()
    except BaseException:
        exporter.close("failed", "Trading run failed")
        raise
    exporter.close("stopped", "Trading run stopped")
