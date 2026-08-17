from datetime import datetime
from typing import Annotated, cast

import typer

from bot import backtest, report, trade
from bot.config import settings
from bot.types import STRATEGY_LABELS, StrategyName


app = typer.Typer(no_args_is_help=True)


def _parse_symbols(value: str) -> list[str]:
    return [symbol for item in value.split(",") if (symbol := item.strip())]


def _parse_strategies(value: str) -> list[StrategyName]:
    selected = [item.strip() for item in value.split(",") if item.strip()]
    allowed = STRATEGY_LABELS
    unknown = set(selected).difference(allowed)
    if not selected or unknown or len(selected) != len(set(selected)):
        names = ", ".join(sorted(allowed))
        raise typer.BadParameter(f"strategies must be unique names from: {names}")
    return cast(list[StrategyName], selected)


@app.command("backtest")
def run_backtest(
    strategy: Annotated[str, typer.Option()] = settings.strategy_names[0],
    start: Annotated[datetime, typer.Option()] = datetime(2023, 1, 1),
    end: Annotated[datetime, typer.Option()] = datetime(2024, 1, 1),
    symbols: Annotated[str, typer.Option()] = "",
) -> None:
    backtest.run(strategy, start, end, _parse_symbols(symbols) or None)


@app.command("report")
def run_report(
    strategy: Annotated[str, typer.Option()] = settings.strategy_names[0],
    symbols: Annotated[str, typer.Option()] = "SPY",
    start: Annotated[datetime, typer.Option()] = datetime(2023, 1, 1),
    end: Annotated[datetime, typer.Option()] = datetime(2024, 1, 1),
    label: Annotated[str | None, typer.Option()] = None,
) -> None:
    report.run(strategy, _parse_symbols(symbols), start, end, label)


@app.command("trade")
def run_trade(strategies: Annotated[str, typer.Option()] = settings.strategies) -> None:
    trade.run(_parse_strategies(strategies))
