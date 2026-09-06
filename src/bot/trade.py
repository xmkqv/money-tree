import signal

from .broker import alpaca_broker
from .config import settings
from .export import StateExporter
from .strategies.registry import strategy_class
from .types import StrategyName


def run(strategy_names: list[StrategyName]) -> None:
    from lumibot.traders import Trader

    from .portfolio import Portfolio

    configuration = settings.trading_configuration
    paused: list[StrategyName] = [
        name for name in strategy_names if strategy_class(name).is_paused
    ]
    exporter = StateExporter(
        str(settings.state_export_url),
        settings.state_export_secret.get_secret_value(),
        strategy_names,
        paused,
        configuration,
    )
    exporter.start()
    exporter.publish("starting", "run", "info", "Trading run is starting")
    try:
        parameters = {**configuration.model_dump(), "strategies": strategy_names}
        strategy = Portfolio(broker=alpaca_broker(), parameters=parameters, name="Portfolio")
        strategy.exporter = exporter
        trader = Trader()
        trader.add_strategy(strategy)
        signal.signal(signal.SIGTERM, lambda number, frame: trader.stop_all())
        exporter.publish("running", "run", "info", "Trading run is active")
        trader.run_all()
    except BaseException:
        exporter.close("failed", "Trading run failed")
        raise
    exporter.close("stopped", "Trading run stopped")
