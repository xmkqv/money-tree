from datetime import datetime
from typing import Annotated

import typer

from bot import backtest, report, trade
from bot.config import settings
from bot.types import STRATEGY_LABELS, StrategyName, resolve_roster


app = typer.Typer(no_args_is_help=True)


def _parse_symbols(value: str) -> list[str]:
    return [symbol for item in value.split(",") if (symbol := item.strip())]


def _read_strategies(value: str) -> tuple[list[StrategyName], dict[str, StrategyName]]:
    """The roster as current names, plus whichever entries used an old one."""
    selected = [item.strip() for item in value.split(",") if item.strip()]
    names, renamed = resolve_roster(selected)
    if not selected or len(names) != len(selected) or len(names) != len(set(names)):
        allowed = ", ".join(sorted(STRATEGY_LABELS))
        raise typer.BadParameter(f"strategies must be unique names from: {allowed}")
    return names, renamed


def _parse_strategies(value: str) -> list[StrategyName]:
    names, _ = _read_strategies(value)
    return names


def _parse_strategy(value: str) -> StrategyName:
    selected = _parse_strategies(value)
    if len(selected) != 1:
        raise typer.BadParameter("strategy must select exactly one strategy")
    return selected[0]


@app.command("backtest")
def run_backtest(
    strategy: Annotated[str, typer.Option()] = settings.strategy_names[0],
    start: Annotated[datetime, typer.Option()] = datetime(2023, 1, 1),
    end: Annotated[datetime, typer.Option()] = datetime(2024, 1, 1),
    symbols: Annotated[str, typer.Option()] = "",
) -> None:
    backtest.run(_parse_strategy(strategy), start, end, _parse_symbols(symbols) or None)


@app.command("report")
def run_report(
    strategy: Annotated[str, typer.Option()] = settings.strategy_names[0],
    symbols: Annotated[str, typer.Option()] = "SPY",
    start: Annotated[datetime, typer.Option()] = datetime(2023, 1, 1),
    end: Annotated[datetime, typer.Option()] = datetime(2024, 1, 1),
) -> None:
    report.run(_parse_strategy(strategy), _parse_symbols(symbols), start, end)


@app.command("trade")
def run_trade(strategies: Annotated[str, typer.Option()] = settings.strategies) -> None:
    trade.run(*_read_strategies(strategies))
