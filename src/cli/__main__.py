from datetime import datetime
from typing import Annotated

import typer

from bot import backtest, report, trade
from bot.config import settings


app = typer.Typer(no_args_is_help=True)


def _parse_symbols(value: str) -> list[str]:
    return [symbol for item in value.split(",") if (symbol := item.strip())]


@app.command("backtest")
def run_backtest(
    strategy: Annotated[str, typer.Option()] = settings.strategy,
    start: Annotated[datetime, typer.Option()] = settings.backtest_start,
    end: Annotated[datetime, typer.Option()] = settings.backtest_end,
    symbols: Annotated[str, typer.Option()] = "",
) -> None:
    backtest.run(strategy, start, end, _parse_symbols(symbols) or None)


@app.command("report")
def run_report(
    strategy: Annotated[str, typer.Option()] = settings.strategy,
    symbols: Annotated[str, typer.Option()] = "SPY",
    start: Annotated[datetime, typer.Option()] = settings.backtest_start,
    end: Annotated[datetime, typer.Option()] = settings.backtest_end,
    label: Annotated[str | None, typer.Option()] = None,
) -> None:
    report.run(strategy, _parse_symbols(symbols), start, end, label)


@app.command("trade")
def run_trade(strategy: Annotated[str, typer.Option()] = settings.strategy) -> None:
    trade.run(strategy)
