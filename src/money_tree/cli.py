from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from money_tree.broker import (
    InstrumentRequirements,
    connect_broker,
    get_account_snapshot,
    load_broker_config,
    reconcile_account,
    verify_account,
    verify_instrument,
)
from money_tree.model import StrategyName, TradingMode
from money_tree.state import StateStore
from money_tree.strategies.base import TradingStrategy
from money_tree.strategies.momentum_long import (
    BAR_INTERVAL as MOMENTUM_BAR_INTERVAL,
)
from money_tree.strategies.momentum_long import (
    INSTRUMENT as INSTRUMENT_DEFAULT,
)
from money_tree.strategies.momentum_long import MomentumLongStrategy
from money_tree.strategies.opening_range import (
    BAR_INTERVAL as OPENING_RANGE_BAR_INTERVAL,
)
from money_tree.strategies.opening_range import OpeningRangeStrategy

MARKET = "NYSE"
MARKET_TIMEZONE = ZoneInfo("America/New_York")
LIVE_CONFIRMATION = TradingMode.LIVE.value


@dataclass(frozen=True, slots=True)
class StrategyConfig:
    strategy_class: type[TradingStrategy]
    bar_interval: str
    requirements: InstrumentRequirements


STRATEGIES = {
    StrategyName.OPENING_RANGE: StrategyConfig(
        OpeningRangeStrategy,
        OPENING_RANGE_BAR_INTERVAL,
        InstrumentRequirements(fractional=True, short=True),
    ),
    StrategyName.MOMENTUM_LONG: StrategyConfig(
        MomentumLongStrategy,
        MOMENTUM_BAR_INTERVAL,
        InstrumentRequirements(fractional=False, short=False),
    ),
}


def default_state_path(strategy: StrategyName, mode: TradingMode) -> Path:
    return Path(f".money-tree/{strategy.value}-{mode.value}-state.json")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="money-tree")
    objects = parser.add_subparsers(dest="object", required=True)
    strategy = objects.add_parser("strategy")
    actions = strategy.add_subparsers(dest="action", required=True)

    backtest = actions.add_parser("backtest")
    backtest.add_argument("strategy_name", type=StrategyName, choices=list(StrategyName))
    backtest.add_argument("--instrument", default=INSTRUMENT_DEFAULT)
    backtest.add_argument("--start", type=date.fromisoformat, default=date(2026, 6, 1))
    backtest.add_argument("--end", type=date.fromisoformat, default=date(2026, 8, 1))
    backtest.add_argument("--out", type=Path)

    trade = actions.add_parser("trade")
    trade.add_argument("strategy_name", type=StrategyName, choices=list(StrategyName))
    trade.add_argument("--mode", type=TradingMode, choices=list(TradingMode), required=True)
    trade.add_argument("--instrument", default=INSTRUMENT_DEFAULT)
    trade.add_argument("--state", type=Path)
    trade.add_argument("--confirm", choices=[LIVE_CONFIRMATION])
    return parser


def run_backtest(
    strategy: StrategyName,
    instrument: str,
    started_on: date,
    ended_before: date,
    out: Path,
) -> dict[str, Any]:
    from lumibot.backtesting import AlpacaBacktesting

    if ended_before <= started_on:
        raise ValueError("backtest end must follow its start")
    config = STRATEGIES[strategy]
    broker_config = load_broker_config(TradingMode.PAPER)
    out.mkdir(parents=True, exist_ok=True)
    Path("logs").mkdir(parents=True, exist_ok=True)
    results, _ = config.strategy_class.run_backtest(
        datasource_class=AlpacaBacktesting,
        backtesting_start=datetime.combine(started_on, datetime.min.time(), MARKET_TIMEZONE),
        backtesting_end=datetime.combine(ended_before, datetime.min.time(), MARKET_TIMEZONE),
        budget=100_000,
        benchmark_asset=instrument,
        parameters={
            "instrument": instrument,
            "persisted": False,
            "state_path": default_state_path(strategy, TradingMode.PAPER),
        },
        config=broker_config.to_lumibot(),
        timestep=config.bar_interval,
        market=MARKET,
        show_plot=False,
        show_tearsheet=False,
        show_indicators=False,
        plot_file_html=str(out / "trades.html"),
        tearsheet_file=str(out / "tearsheet.html"),
        trades_file=str(out / "trades.csv"),
        stats_file=str(out / "stats.csv"),
        settings_file=str(out / "settings.json"),
        indicators_file=str(out / "indicators.html"),
        tearsheet_metrics_file=str(out / "metrics.json"),
    )
    return results


def run_trade(
    strategy: StrategyName,
    instrument: str,
    mode: TradingMode,
    state_path: Path,
    *,
    confirmation: str | None,
) -> None:
    if mode is TradingMode.LIVE and confirmation != LIVE_CONFIRMATION:
        raise RuntimeError("live trading requires --confirm live")
    if mode is TradingMode.PAPER and confirmation is not None:
        raise ValueError("--confirm is valid only for live trading")
    strategy_config = STRATEGIES[strategy]
    broker_config = load_broker_config(mode)
    client = connect_broker(broker_config)
    verify_account(client)
    verify_instrument(client, instrument, strategy_config.requirements)
    store = StateStore(state_path, strategy=strategy, instrument=instrument)
    state = store.load()
    reconcile_account(get_account_snapshot(client, instrument), state)
    store.save(state)

    from lumibot.brokers import Alpaca

    broker = Alpaca(broker_config.to_lumibot())
    if mode is TradingMode.PAPER and not broker.is_paper:
        raise RuntimeError("paper mode resolved to a live account")
    if mode is TradingMode.LIVE and broker.is_paper:
        raise RuntimeError("live mode resolved to a paper account")
    running_strategy = strategy_config.strategy_class(
        broker=broker,
        parameters={
            "instrument": instrument,
            "state_path": state_path,
            "persisted": True,
        },
    )
    running_strategy.run_live()


def main() -> None:
    arguments = build_parser().parse_args()
    if arguments.object != "strategy":
        raise RuntimeError(f"unsupported object {arguments.object!r}")
    strategy = StrategyName(arguments.strategy_name)
    if arguments.action == "backtest":
        out = arguments.out or Path("out") / strategy.value
        results = run_backtest(
            strategy,
            arguments.instrument,
            arguments.start,
            arguments.end,
            out,
        )
        for name in ("total_return", "max_drawdown", "sharpe"):
            if name in results:
                print(f"{name}: {results[name]}")
        print(f"reports: {out}")
        return
    if arguments.action == "trade":
        mode = TradingMode(arguments.mode)
        state_path = arguments.state or default_state_path(strategy, mode)
        run_trade(
            strategy,
            arguments.instrument,
            mode,
            state_path,
            confirmation=arguments.confirm,
        )
        return
    raise RuntimeError(f"unsupported strategy action {arguments.action!r}")


if __name__ == "__main__":
    main()
