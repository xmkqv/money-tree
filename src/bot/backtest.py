from datetime import datetime

from bot.config import settings


def run(strategy_name: str, start: datetime, end: datetime) -> object:
    from lumibot.backtesting import YahooDataBacktesting

    from bot.strategies.shared import load_strategy

    return load_strategy(strategy_name).backtest(
        YahooDataBacktesting,
        start,
        end,
        parameters=settings.risk_parameters,
        analyze_backtest=False,
    )
