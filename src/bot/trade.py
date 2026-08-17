import signal

from bot.broker import build_alpaca_broker
from bot.config import settings
from bot.export import StateExporter


def run(strategy_name: str) -> None:
    from lumibot.traders import Trader

    from bot.strategies.shared import load_strategy

    exporter = None
    if settings.state_export_url is not None and settings.state_export_secret is not None:
        exporter = StateExporter(
            str(settings.state_export_url),
            settings.state_export_secret.get_secret_value(),
            strategy_name,
        )
        exporter.start()
        exporter.publish("starting", "run", "info", "Trading run is starting")
    try:
        strategy = load_strategy(strategy_name)(
            broker=build_alpaca_broker(), parameters=settings.risk_parameters
        )
        strategy.exporter = exporter
        trader = Trader()
        trader.add_strategy(strategy)
        signal.signal(signal.SIGTERM, lambda number, frame: trader.stop_all())
        if exporter is not None:
            exporter.publish("running", "run", "info", "Trading run is active")
        trader.run_all()
    finally:
        if exporter is not None:
            exporter.close("failed", "Trading run failed")
