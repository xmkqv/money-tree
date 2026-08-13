from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from money_tree.broker import (
    connect_trading_client,
    get_account_snapshot,
    load_broker_config,
    verify_account,
    verify_account_snapshot,
    verify_asset,
)
from money_tree.state import StateStore
from money_tree.strategies.orb import MARKET, STATE_PATH, SYMBOL, OpeningRangeBreakout

MARKET_TIMEZONE = ZoneInfo("America/New_York")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="money-tree")
    commands = parser.add_subparsers(dest="command", required=True)
    backtest = commands.add_parser("backtest")
    backtest.add_argument("--symbol", default=SYMBOL)
    backtest.add_argument("--start", default="2026-06-01")
    backtest.add_argument("--end", default="2026-08-01")
    backtest.add_argument("--out", type=Path, default=Path("out"))
    live = commands.add_parser("live")
    live.add_argument("--symbol", default=SYMBOL)
    live.add_argument("--state", type=Path, default=STATE_PATH)
    live.add_argument("--confirm-live", action="store_true")
    return parser


def run_backtest(symbol: str, start_text: str, end_text: str, out: Path) -> dict[str, Any]:
    from lumibot.backtesting import AlpacaBacktesting

    config = load_broker_config(paper=True)
    start = datetime.fromisoformat(start_text).replace(tzinfo=MARKET_TIMEZONE)
    end = datetime.fromisoformat(end_text).replace(tzinfo=MARKET_TIMEZONE)
    if end <= start:
        raise ValueError("backtest end must follow its start")
    out.mkdir(parents=True, exist_ok=True)
    Path("logs").mkdir(parents=True, exist_ok=True)
    results, _ = OpeningRangeBreakout.run_backtest(
        datasource_class=AlpacaBacktesting,
        backtesting_start=start,
        backtesting_end=end,
        budget=100_000,
        benchmark_asset=symbol,
        parameters={"symbol": symbol, "persist_state": False},
        config=config.lumibot(),
        timestep="minute",
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


def run_live(symbol: str, state_path: Path, *, confirmed: bool) -> None:
    if not confirmed:
        raise RuntimeError("live trading requires --confirm-live")
    config = load_broker_config(paper=False)
    client = connect_trading_client(config)
    verify_account(client)
    verify_asset(client, symbol)
    store = StateStore(state_path)
    state = store.load()
    verify_account_snapshot(get_account_snapshot(client, symbol), state)
    store.save(state)
    from lumibot.brokers import Alpaca

    broker = Alpaca(config.lumibot())
    if broker.is_paper:
        raise RuntimeError("live broker resolved to a paper account")
    strategy = OpeningRangeBreakout(
        broker=broker,
        parameters={"symbol": symbol, "state_path": state_path, "persist_state": True},
    )
    strategy.run_live()


def main() -> None:
    arguments = build_parser().parse_args()
    if arguments.command == "backtest":
        results = run_backtest(arguments.symbol, arguments.start, arguments.end, arguments.out)
        for name in ("total_return", "max_drawdown", "sharpe"):
            if name in results:
                print(f"{name}: {results[name]}")
        print(f"reports: {arguments.out}")
        return
    if arguments.command == "live":
        run_live(arguments.symbol, arguments.state, confirmed=arguments.confirm_live)
        return
    raise RuntimeError(f"unsupported command {arguments.command!r}")


if __name__ == "__main__":
    main()
