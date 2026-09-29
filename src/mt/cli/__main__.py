from datetime import date, datetime, time
from typing import TYPE_CHECKING, Annotated

import typer
from pydantic import ValidationError

from mt.rules.services import ServiceName, service_secrets
from mt.rules.values import StrategyKey, strategy_selection_adapter


if TYPE_CHECKING:
    from mt.data.asset import Asset


app = typer.Typer(no_args_is_help=True, add_completion=False)
environment = typer.Typer(no_args_is_help=True)
app.add_typer(environment, name="env")


@environment.command("list")
def list_environment(service: Annotated[ServiceName, typer.Option()]) -> None:
    for key in service_secrets(service):
        typer.echo(key)


def _parse_assets(value: str) -> list[Asset]:
    from mt.data.asset import Asset

    try:
        assets = [Asset.from_symbol(item) for item in value.split(",")]
        if len(set(assets)) != len(assets):
            raise ValueError("symbols must be distinct")
        return assets
    except ValueError as error:
        raise typer.BadParameter(str(error)) from error


def _parse_strategies(value: str) -> list[StrategyKey]:
    try:
        return list(strategy_selection_adapter.validate_python(value))
    except ValidationError as error:
        raise typer.BadParameter("; ".join(item["msg"] for item in error.errors())) from error


def _parse_strategy(value: str) -> StrategyKey:
    selected = _parse_strategies(value)
    if len(selected) != 1:
        raise typer.BadParameter("strategy must select exactly one strategy")
    return selected[0]


@app.command("report")
def run_report(
    strategy: Annotated[str, typer.Option()],
    symbols: Annotated[str, typer.Option()],
    start: Annotated[date, typer.Option(parser=date.fromisoformat)],
    end: Annotated[date, typer.Option(parser=date.fromisoformat)],
) -> None:
    from mt.bot.backtest import report

    typer.echo(
        report(
            _parse_strategy(strategy),
            _parse_assets(symbols),
            datetime.combine(start, time()),
            datetime.combine(end, time()),
        )
    )


@app.command("trade")
def run_trade(
    strategies: Annotated[str | None, typer.Option()] = None,
) -> None:
    from mt.bot.trade import trade
    from mt.rules.bot import settings as bot_settings

    trade(list(bot_settings.strategies) if strategies is None else _parse_strategies(strategies))
