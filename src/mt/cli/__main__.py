from datetime import datetime
from typing import Annotated

import typer
from pydantic import TypeAdapter, ValidationError

from mt.config.bot import settings
from mt.config.services import SERVICE_SETTINGS, ServiceName, service_secrets
from mt.config.values import STRATEGY_KEYS, StrategyKey, Symbol, strategy_selection_adapter


app = typer.Typer(no_args_is_help=True)
environment = typer.Typer(no_args_is_help=True)
app.add_typer(environment, name="env")


@environment.command("list")
def list_environment(service: Annotated[str, typer.Option()]) -> None:
    for key in service_secrets(_parse_service(service)):
        typer.echo(key)


def _parse_service(value: str) -> ServiceName:
    for name in SERVICE_SETTINGS:
        if value == name:
            return name
    names = ", ".join(sorted(SERVICE_SETTINGS))
    raise typer.BadParameter(f"service must be one of: {names}")


def _parse_symbols(value: str) -> list[str]:
    try:
        symbols = TypeAdapter(list[Symbol]).validate_python(
            [item.strip() for item in value.split(",")]
        )
        if len(set(symbols)) != len(symbols):
            raise ValueError("symbols must be distinct")
        return symbols
    except ValueError as error:
        raise typer.BadParameter("symbols must be distinct uppercase ticker symbols") from error


def _parse_strategies(value: str) -> list[StrategyKey]:
    try:
        return list(strategy_selection_adapter.validate_python(value))
    except ValidationError as error:
        names = ", ".join(sorted(STRATEGY_KEYS))
        message = f"strategies must be distinct keys; choose from: {names}"
        raise typer.BadParameter(message) from error


def _parse_strategy(value: str) -> StrategyKey:
    selected = _parse_strategies(value)
    if len(selected) != 1:
        raise typer.BadParameter("strategy must select exactly one strategy")
    return selected[0]


@app.command("report")
def run_report(
    strategy: Annotated[str, typer.Option()] = settings.strategies[0],
    symbols: Annotated[str, typer.Option()] = settings.benchmark_symbol,
    start: Annotated[datetime, typer.Option()] = settings.backtest.start_at,
    end: Annotated[datetime, typer.Option()] = settings.backtest.end_at,
) -> None:
    if start.tzinfo != end.tzinfo or end <= start:
        raise typer.BadParameter("end must follow start in the same timezone")
    selected = _parse_strategy(strategy)
    tickers = _parse_symbols(symbols)
    from mt.bot.backtest import report

    typer.echo(report(selected, tickers, start, end))


@app.command("trade")
def run_trade(
    strategies: Annotated[str, typer.Option()] = ",".join(settings.strategies),
) -> None:
    from mt.bot.trade import trade

    trade(_parse_strategies(strategies))
