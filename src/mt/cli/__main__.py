from datetime import datetime
from typing import Annotated

import typer

from mt.config.services import SERVICE_SETTINGS, ServiceName, service_keys
from mt.config.settings import settings
from mt.strategies.keys import STRATEGY_KEYS, StrategyName, is_strategy_name


app = typer.Typer(no_args_is_help=True)
environment = typer.Typer(no_args_is_help=True)
app.add_typer(environment, name="env")


@environment.command("list")
def list_environment(service: Annotated[str, typer.Option()]) -> None:
    for key in service_keys(_parse_service(service)):
        typer.echo(key)


def _parse_service(value: str) -> ServiceName:
    for name in SERVICE_SETTINGS:
        if value == name:
            return name
    names = ", ".join(sorted(SERVICE_SETTINGS))
    raise typer.BadParameter(f"service must be one of: {names}")


def _parse_symbols(value: str) -> list[str]:
    return [symbol for item in value.split(",") if (symbol := item.strip())]


def _parse_strategies(value: str) -> list[StrategyName]:
    selected = [item.strip() for item in value.split(",") if item.strip()]
    allowed = STRATEGY_KEYS
    unknown = set(selected).difference(allowed)
    if not selected or unknown or len(selected) != len(set(selected)):
        names = ", ".join(sorted(allowed))
        raise typer.BadParameter(f"strategies must be unique names from: {names}")
    return [item for item in selected if is_strategy_name(item)]


def _parse_strategy(value: str) -> StrategyName:
    selected = _parse_strategies(value)
    if len(selected) != 1:
        raise typer.BadParameter("strategy must select exactly one strategy")
    return selected[0]


@app.command("backtest")
def run_backtest(
    symbols: Annotated[str, typer.Option()],
    strategy: Annotated[str, typer.Option()] = settings.strategy_names[0],
    start: Annotated[datetime, typer.Option()] = datetime(2023, 1, 1),
    end: Annotated[datetime, typer.Option()] = datetime(2024, 1, 1),
) -> None:
    from mt.bot import backtest

    backtest.run(_parse_strategy(strategy), _parse_symbols(symbols), start, end)


@app.command("report")
def run_report(
    strategy: Annotated[str, typer.Option()] = settings.strategy_names[0],
    symbols: Annotated[str, typer.Option()] = settings.benchmark_symbol,
    start: Annotated[datetime, typer.Option()] = datetime(2023, 1, 1),
    end: Annotated[datetime, typer.Option()] = datetime(2024, 1, 1),
) -> None:
    from mt.bot.backtest import report

    report(_parse_strategy(strategy), _parse_symbols(symbols), start, end)


@app.command("trade")
def run_trade(strategies: Annotated[str, typer.Option()] = settings.strategies) -> None:
    from mt.bot import trade

    trade.run(_parse_strategies(strategies))
