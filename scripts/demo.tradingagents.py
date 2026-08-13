"""
uv sync --group demo
uv run scripts/demo_alpaca.py --ticker NVDA
uv run scripts/demo_alpaca.py --ticker NVDA --submit true
"""

import argparse
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final

from alpaca.data.enums import DataFeed
from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.models import Order, Position, TradeAccount
from alpaca.trading.requests import MarketOrderRequest
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph

ALPACA_API_KEY: Final = os.environ["ALPACA_API_KEY"]
ALPACA_API_SECRET: Final = os.environ["ALPACA_API_SECRET"]
OPENROUTER_API_KEY: Final = os.environ["OPENROUTER_API_KEY"]

TICKER: Final = os.environ.get("TICKER", "NVDA")
QTY: Final = 1
N_DAY_LOOKBACK: Final = 7
DEEP_LLM: Final = os.environ.get("DEEP_LLM", "anthropic/claude-opus-5")
QUICK_LLM: Final = os.environ.get("QUICK_LLM", "anthropic/claude-haiku-4.5")
ANALYSTS: Final = ("market", "social", "news", "fundamentals")
OUT: Final = Path(os.environ.get("OUT", "out")) / "agents"

SIDE_BY_RATING: Final[dict[str, OrderSide | None]] = {
    "Buy": OrderSide.BUY,
    "Overweight": OrderSide.BUY,
    "Hold": None,
    "Underweight": OrderSide.SELL,
    "Sell": OrderSide.SELL,
}

BOOL_BY_TEXT: Final = {"true": True, "false": False}


def parse_bool(text: str) -> bool:
    return BOOL_BY_TEXT[text]


def get_close(ticker: str) -> float:
    client = StockHistoricalDataClient(ALPACA_API_KEY, ALPACA_API_SECRET)
    request = StockBarsRequest(
        symbol_or_symbols=ticker,
        timeframe=TimeFrame.Day,
        start=datetime.now(UTC) - timedelta(days=N_DAY_LOOKBACK),
        feed=DataFeed.IEX,
    )
    return client.get_stock_bars(request).data[ticker][-1].close


def decide(ticker: str, trade_date: str) -> tuple[str, str]:
    config = DEFAULT_CONFIG.copy()
    config["llm_provider"] = "openrouter"
    config["deep_think_llm"] = DEEP_LLM
    config["quick_think_llm"] = QUICK_LLM
    config["results_dir"] = str(OUT)
    config["data_cache_dir"] = str(OUT / "cache")
    config["memory_log_path"] = str(OUT / "memory.md")

    graph = TradingAgentsGraph(selected_analysts=ANALYSTS, debug=False, config=config)
    final_state, rating = graph.propagate(ticker, trade_date)
    return rating, final_state["final_trade_decision"]


def get_side(rating: str) -> OrderSide | None:
    return SIDE_BY_RATING[rating]


def build_order(ticker: str, side: OrderSide) -> MarketOrderRequest:
    return MarketOrderRequest(
        symbol=ticker,
        qty=QTY,
        side=side,
        time_in_force=TimeInForce.DAY,
    )


def submit(client: TradingClient, order: MarketOrderRequest) -> Order:
    return client.submit_order(order)


def print_account(account: TradeAccount, positions: list[Position]) -> None:
    print(f"account   {account.account_number}  status={account.status}")
    print(f"equity    {account.equity} USD  buying_power={account.buying_power} USD")
    if not positions:
        print("positions none")
        return
    for position in positions:
        print(
            f"position  {position.symbol} qty={position.qty} "
            f"avg={position.avg_entry_price} pl={position.unrealized_pl}"
        )


def print_decision(ticker: str, close: float, rating: str, rationale: str) -> None:
    print(f"close     {ticker} {close}")
    print(f"rating    {rating}")
    print(f"rationale\n{rationale}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", default=TICKER)
    parser.add_argument("--date", default=datetime.now(UTC).date().isoformat())
    parser.add_argument("--submit", type=parse_bool, default=False, metavar="{true,false}")
    arguments = parser.parse_args()

    close = get_close(arguments.ticker)
    rating, rationale = decide(arguments.ticker, arguments.date)
    print_decision(arguments.ticker, close, rating, rationale)

    client = TradingClient(ALPACA_API_KEY, ALPACA_API_SECRET, paper=True)
    print_account(client.get_account(), client.get_all_positions())

    side = get_side(rating)
    if side is None:
        print(f"order     none ({rating})")
        return

    order = build_order(arguments.ticker, side)
    print(f"order     {side.value} {QTY} {arguments.ticker} market day")
    if not arguments.submit:
        print("submit    skipped (pass --submit true)")
        return

    print(f"submitted {submit(client, order).id}")


if __name__ == "__main__":
    main()
