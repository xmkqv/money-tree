import signal

from .broker import build_alpaca_broker
from .config import settings
from .export import StateExporter
from .types import StrategyName, published_roster


def run(strategy_names: list[StrategyName]) -> None:
    from lumibot.traders import Trader

    from .portfolio import Strategy

    configuration = settings.trading_configuration
    labels, paused = published_roster(strategy_names)
    exporter = StateExporter(
        str(settings.state_export_url),
        settings.state_export_secret.get_secret_value(),
        labels,
        paused,
        configuration,
    )
    exporter.start()
    exporter.publish("starting", "run", "info", "Trading run is starting")
    try:
        parameters = {**configuration.model_dump(), "strategies": strategy_names}
        strategy = Strategy(broker=build_alpaca_broker(), parameters=parameters, name="Portfolio")
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
