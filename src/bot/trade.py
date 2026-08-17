import signal

from bot.broker import build_alpaca_broker
from bot.config import settings
from bot.export import StateExporter
from bot.types import STRATEGY_LABELS, StrategyName


def run(strategy_names: list[StrategyName]) -> None:
    from lumibot.traders import Trader

    from bot.strategies.portfolio import Strategy

    configuration = settings.trading_configuration
    labels = [STRATEGY_LABELS[name] for name in strategy_names]
    exporter = None
    if settings.state_export_url is not None and settings.state_export_secret is not None:
        exporter = StateExporter(
            str(settings.state_export_url),
            settings.state_export_secret.get_secret_value(),
            labels,
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
        if exporter is not None:
            exporter.publish("running", "run", "info", "Trading run is active")
        trader.run_all()
    except BaseException:
        if exporter is not None:
            exporter.close("failed", "Trading run failed")
        raise
    if exporter is not None:
        exporter.close("stopped", "Trading run stopped")
