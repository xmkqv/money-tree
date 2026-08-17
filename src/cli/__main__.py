from datetime import datetime
from typing import Annotated

import typer

from bot.backtest import run as run_backtest
from bot.config import settings
from bot.trade import run as run_trade


app = typer.Typer(no_args_is_help=True)


@app.command()
def backtest(
    strategy: Annotated[str, typer.Option()] = settings.strategy,
    start: Annotated[datetime, typer.Option()] = settings.backtest_start,
    end: Annotated[datetime, typer.Option()] = settings.backtest_end,
) -> None:
    run_backtest(strategy, start, end)


@app.command()
def trade(strategy: Annotated[str, typer.Option()] = settings.strategy) -> None:
    run_trade(strategy)


if __name__ == "__main__":
    app()
