from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Annotated

import typer
from pydantic import ValidationError

from mt.rules.services import SERVICE_SETTINGS, ServiceName, service_secrets
from mt.rules.values import STRATEGY_KEYS, StrategyKey, strategy_selection_adapter


if TYPE_CHECKING:
    from mt.data.asset import Asset


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


def _parse_assets(value: str) -> list[Asset]:
    from mt.data.asset import Asset, AssetType

    try:
        assets = [Asset.from_symbol(item.strip()) for item in value.split(",")]
        if len(set(assets)) != len(assets):
            raise ValueError("symbols must be distinct")
        if any(asset.asset_type != AssetType.STOCK for asset in assets):
            raise ValueError("reports support equities only")
        return assets
    except ValueError as error:
        raise typer.BadParameter(str(error)) from error


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
    strategy: Annotated[str | None, typer.Option()] = None,
    symbols: Annotated[str | None, typer.Option()] = None,
    start: Annotated[datetime | None, typer.Option()] = None,
    end: Annotated[datetime | None, typer.Option()] = None,
) -> None:
    from mt.rules.bot import settings as bot_settings
    from mt.rules.shared import settings

    strategy = bot_settings.strategies[0] if strategy is None else strategy
    symbols = settings.benchmark_symbol if symbols is None else symbols
    start = bot_settings.backtest.start_at if start is None else start
    end = bot_settings.backtest.end_at if end is None else end
    if start.tzinfo != end.tzinfo or end <= start:
        raise typer.BadParameter("end must follow start in the same timezone")
    selected = _parse_strategy(strategy)
    assets = _parse_assets(symbols)
    from mt.bot.backtest import report

    typer.echo(report(selected, assets, start, end))


@app.command("trade")
def run_trade(
    strategies: Annotated[str | None, typer.Option()] = None,
) -> None:
    from mt.bot.trade import trade
    from mt.rules.bot import settings as bot_settings

    strategies = ",".join(bot_settings.strategies) if strategies is None else strategies
    trade(_parse_strategies(strategies))
