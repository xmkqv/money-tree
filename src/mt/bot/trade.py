import signal

from mt.config.bot import settings
from mt.config.settings import RuleSettings
from mt.config.values import StrategyKey
from mt.strategies.registry import strategy_class

from .broker import alpaca_broker
from .export import StateExporter


def trade(strategies: list[StrategyKey]) -> None:
    from lumibot.traders import Trader

    from .portfolio import Portfolio

    paused: list[StrategyKey] = [key for key in strategies if strategy_class(key).is_paused]
    exporter = StateExporter(
        str(settings.export.url),
        settings.export.secret.get_secret_value(),
        strategies,
        paused,
        RuleSettings.model_validate(settings.model_dump()),
    )
    exporter.start()
    exporter.publish("starting", "run.started", "info", "Trading run is starting")
    try:
        parameters: dict[str, object] = {"strategies": strategies}
        strategy = Portfolio(broker=alpaca_broker(), parameters=parameters, name="Portfolio")
        strategy.exporter = exporter
        trader = Trader()
        trader.add_strategy(strategy)
        signal.signal(signal.SIGTERM, lambda number, frame: trader.stop_all())
        exporter.publish("running", "run.activated", "info", "Trading run is active")
        trader.run_all()
    except BaseException:
        exporter.close("failed", "Trading run failed")
        raise
    exporter.close("stopped", "Trading run stopped")
