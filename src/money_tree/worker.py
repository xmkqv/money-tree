from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

from money_tree.cli import (
    INSTRUMENT_DEFAULT,
    LIVE_CONFIRMATION,
    default_state_path,
    run_trade,
)
from money_tree.model import StrategyName, TradingMode

STRATEGY_VARIABLE = "MONEY_TREE_STRATEGY"
LIVE_VARIABLE = "MONEY_TREE_IS_LIVE"


@dataclass(frozen=True, slots=True)
class WorkerConfig:
    strategy: StrategyName
    mode: TradingMode


def load_worker_config(environment: Mapping[str, str] | None = None) -> WorkerConfig:
    values = os.environ if environment is None else environment
    strategy_text = values.get(STRATEGY_VARIABLE)
    if not strategy_text:
        raise RuntimeError(f"missing {STRATEGY_VARIABLE}")
    try:
        strategy = StrategyName(strategy_text)
    except ValueError as error:
        choices = ", ".join(item.value for item in StrategyName)
        raise RuntimeError(f"{STRATEGY_VARIABLE} must be one of: {choices}") from error

    live_text = values.get(LIVE_VARIABLE, "false")
    if live_text not in {"false", "true"}:
        raise RuntimeError(f"{LIVE_VARIABLE} must be true or false")
    mode = TradingMode.LIVE if live_text == "true" else TradingMode.PAPER
    return WorkerConfig(strategy=strategy, mode=mode)


def run_worker(config: WorkerConfig) -> None:
    confirmation = LIVE_CONFIRMATION if config.mode is TradingMode.LIVE else None
    run_trade(
        config.strategy,
        INSTRUMENT_DEFAULT,
        config.mode,
        default_state_path(config.strategy, config.mode),
        confirmation=confirmation,
    )


def main() -> None:
    run_worker(load_worker_config())


if __name__ == "__main__":
    main()
