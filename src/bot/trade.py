from bot.backtest import load_strategy
from bot.broker import build_alpaca_broker
from bot.config import settings


def build_trader() -> object:
    from lumibot.traders import Trader

    return Trader()


def run(strategy_name: str) -> None:
    broker = build_alpaca_broker()
    strategy = load_strategy(strategy_name)(
        broker=broker,
        parameters=settings.risk_parameters,
    )
    trader = build_trader()
    trader.add_strategy(strategy)
    trader.run_all()
