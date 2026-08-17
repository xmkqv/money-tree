from bot.backtest import load_strategy
from bot.broker import build_alpaca_broker
from bot.config import settings
from bot.export import StateExporter


def run(strategy_name: str) -> None:
    from lumibot.traders import Trader

    exporter = None
    if settings.state_export_url is not None and settings.state_export_secret is not None:
        exporter = StateExporter(
            str(settings.state_export_url),
            settings.state_export_secret.get_secret_value(),
            strategy_name,
        )
        exporter.start()
        exporter.publish("starting", "run", "info", "Trading run is starting")
    failed = True
    try:
        broker = build_alpaca_broker()
        strategy = load_strategy(strategy_name)(
            broker=broker,
            parameters=settings.risk_parameters,
        )
        trader = Trader()
        trader.add_strategy(strategy)
        if exporter is not None:
            exporter.publish("running", "run", "info", "Trading run is active")
        trader.run_all()
        failed = False
    finally:
        if exporter is not None:
            if failed:
                exporter.close("failed", "Trading run failed")
            else:
                exporter.close("stopped", "Trading run stopped")
