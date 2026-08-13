"""
demo.lumibot.py

    uv add lumibot   # resolves to 4.5.26 beside nautilus-trader; verified there

The live node's strategy ported to Lumibot: EMA side picks the entry, an ATR
trailing stop rides the position, a rejected trailing stop flattens it. Alpaca
serves both halves — AlpacaBacktesting for the simulated feed, the Alpaca broker
for the live node — so the same class runs either way.

Lumibot is one loop, not an event bus: on_trading_iteration polls a bar frame
per sleeptime, and only order outcomes arrive as callbacks. There is no
indicator registration and no per-tick handler, so the EMAs and the ATR are
recomputed from the frame each iteration rather than fed bar by bar.

ALPACA_API_KEY and ALPACA_API_SECRET must be set; Lumibot loads .env on import.
Both modes are paper — AlpacaBacktesting refuses a live key outright.

Named artifacts go to OUT. Lumibot hardcodes logs/ for the two it does not let a
caller redirect (trade events, tearsheet csv) and does not create the directory,
so the run does; both are gitignored.

    SYMBOL=SPY START=2023-01-01 END=2024-09-01 uv run scripts/demo.lumibot.py
    MODE=live SYMBOL=SPY uv run scripts/demo.lumibot.py
    MODE=live ONCE=true TRADE_SIZE=1 uv run scripts/demo.lumibot.py

ONCE=true submits one iteration and exits, which returns before the entry fill
arrives — the trailing stop is attached from the fill callback, so a one-shot run
leaves the position unprotected. It proves the wiring; it is not how to run this.

Alpaca rejects a trailing offset under 0.1% of the share price, which a raw ATR
multiple undershoots on minute bars, so the offset is floored at that. The broker
rejects such an order synchronously rather than through the event stream, so both
submits check their result inline; on_error_order alone never sees these. An entry
whose submit is refused leaves entry_order unset so the next bar retries, and a
flat iteration holding stale order state cancels and clears it, since neither a
rejection nor an out-of-band close produces an event to reconcile from.

SIGINT reaches on_abrupt_closing, which cancels and flattens; SIGKILL and SIGTERM
do not, and leave the position and its stop live at the broker.
"""

from __future__ import annotations

import math
import os
from datetime import datetime
from pathlib import Path
from typing import ClassVar, Final

import pandas as pd
import pytz
from lumibot.entities import Asset, Order, Position
from lumibot.strategies import Strategy

SYMBOL: Final = "SPY"
MARKET: Final = "NYSE"
TIMESTEP: Final = "day"
SLEEPTIME: Final = "1D"
FAST_EMA: Final = 10
SLOW_EMA: Final = 20
TRAIL_ATR: Final = 3.0
TRAIL_FLOOR_PCT: Final = 0.001
TIMEZONE: Final = pytz.timezone("America/New_York")
TRADE_SIZE: Final = 100
STARTING_BALANCE: Final = 100_000
BENCHMARK: Final = "SPY"
LOGDIR: Final = Path("logs")


class EmaSideTrailing(Strategy):
    parameters: ClassVar[dict] = {
        "symbol": SYMBOL,
        "trade_size": TRADE_SIZE,
        "timestep": TIMESTEP,
        "sleeptime": SLEEPTIME,
        "atr_period": 14,
        "trailing_atr_multiple": TRAIL_ATR,
        "fast_ema_period": FAST_EMA,
        "slow_ema_period": SLOW_EMA,
        "warmup_bars": 200,
        "max_trailing_stop_failures": 3,
    }

    def initialize(self) -> None:
        if self.parameters["fast_ema_period"] >= self.parameters["slow_ema_period"]:
            raise ValueError(
                f"fast_ema_period={self.parameters['fast_ema_period']} must be less than "
                f"slow_ema_period={self.parameters['slow_ema_period']}"
            )

        self.sleeptime = self.parameters["sleeptime"]
        self.set_market(MARKET)

        self.asset = Asset(self.parameters["symbol"])
        self.entry_order: Order | None = None
        self.trailing_stop: Order | None = None
        self.trailing_stop_failures = 0
        self.atr = 0.0

    def on_trading_iteration(self) -> None:
        bars = self.get_historical_prices(
            self.asset, self.parameters["warmup_bars"], self.parameters["timestep"]
        )
        if bars is None or bars.empty:
            self.log_message("Warming up indicators", color="blue")
            return

        frame = bars.pandas_df
        if len(frame) < self.parameters["slow_ema_period"]:
            self.log_message("Warming up indicators", color="blue")
            return

        self.atr = average_true_range(frame, self.parameters["atr_period"])

        if self.get_position(self.asset) is not None:
            return

        if self.entry_order is not None or self.trailing_stop is not None:
            self.cancel_open_orders()
            self.entry_order = None
            self.trailing_stop = None

        fast_ema = exponential_moving_average(frame["close"], self.parameters["fast_ema_period"])
        slow_ema = exponential_moving_average(frame["close"], self.parameters["slow_ema_period"])
        entry_side = Order.OrderSide.BUY if fast_ema >= slow_ema else Order.OrderSide.SELL
        self.log_message(
            f"fast={fast_ema:.2f} slow={slow_ema:.2f} atr={self.atr:.3f} -> {entry_side}",
            color="blue",
        )
        self._submit_entry(entry_side)

    def on_filled_order(
        self,
        position: Position,
        order: Order,
        price: float,
        quantity: float,
        multiplier: float,
    ) -> None:
        if self._is_trailing_stop(order):
            self.trailing_stop = None
            self.entry_order = None
            return

        if self._is_entry(order) and self.trailing_stop is None:
            self.trailing_stop_failures = 0
            self._attach_trailing_stop(position)

    def on_canceled_order(self, order: Order) -> None:
        if self._is_trailing_stop(order):
            self._flatten_position("canceled")
        elif self._is_entry(order):
            self.entry_order = None

    def on_error_order(self, order: Order, error: Exception | None = None) -> None:
        if self._is_trailing_stop(order):
            self._flatten_position(str(error))
        elif self._is_entry(order):
            self.entry_order = None

    def on_abrupt_closing(self) -> None:
        self.log_message("Shutting down: cancelling orders and flattening", color="yellow")
        self.cancel_open_orders()
        self.sell_all()

    def _is_trailing_stop(self, order: Order) -> bool:
        return self.trailing_stop is not None and order.identifier == self.trailing_stop.identifier

    def _is_entry(self, order: Order) -> bool:
        return self.entry_order is not None and order.identifier == self.entry_order.identifier

    def _flatten_position(self, reason: str) -> None:
        self.trailing_stop = None
        self.trailing_stop_failures += 1
        self.log_message(f"Trailing stop failed ({reason}); closing position", color="red")
        self.sell_all()

        if self.trailing_stop_failures >= self.parameters["max_trailing_stop_failures"]:
            raise RuntimeError(
                f"Stopping after {self.trailing_stop_failures} trailing stop failures"
            )

    def _attach_trailing_stop(self, position: Position) -> None:
        quantity = abs(float(position.quantity))
        if quantity == 0.0:
            return

        exit_side = Order.OrderSide.SELL if float(position.quantity) > 0 else Order.OrderSide.BUY
        self._submit_trailing_stop(exit_side, quantity)

    def _submit_entry(self, order_side: str) -> None:
        if self.entry_order is not None:
            return

        order = self.create_order(self.asset, self.parameters["trade_size"], order_side)
        submitted = self.submit_order(order)
        if submitted is None or submitted.status == Order.OrderStatus.ERROR:
            self.log_message(f"Broker rejected the {order_side} entry", color="red")
            return

        self.entry_order = submitted

    def _trailing_offset(self) -> float:
        price = self.get_last_price(self.asset)
        if price is None:
            return 0.0

        atr_offset = self.atr * self.parameters["trailing_atr_multiple"]
        floor = float(price) * TRAIL_FLOOR_PCT
        return math.ceil(max(atr_offset, floor) * 100) / 100

    def _submit_trailing_stop(self, order_side: str, quantity: float) -> None:
        offset = self._trailing_offset()
        if offset <= 0.0:
            self._flatten_position("no ATR or price to size the trailing offset")
            return

        order = self.create_order(
            self.asset,
            quantity,
            order_side,
            trail_price=offset,
            order_type=Order.OrderType.TRAIL,
        )
        submitted = self.submit_order(order)
        if submitted is None or submitted.status == Order.OrderStatus.ERROR:
            self._flatten_position(f"broker rejected a {offset} trailing offset")
            return

        self.trailing_stop = submitted
        self.log_message(f"Trailing stop attached {offset} behind {order_side}", color="green")


def exponential_moving_average(closes: pd.Series, period: int) -> float:
    return float(closes.ewm(span=period, adjust=False).mean().iloc[-1])


def average_true_range(frame: pd.DataFrame, period: int) -> float:
    previous_close = frame["close"].shift(1)
    true_range = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - previous_close).abs(),
            (frame["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return float(true_range.ewm(alpha=1 / period, adjust=False).mean().iloc[-1])


def alpaca_config() -> dict:
    return {
        "API_KEY": os.environ["ALPACA_API_KEY"],
        "API_SECRET": os.environ["ALPACA_API_SECRET"],
        "PAPER": True,
    }


def parameters() -> dict:
    return {
        "symbol": os.environ.get("SYMBOL", SYMBOL),
        "trade_size": int(os.environ.get("TRADE_SIZE", TRADE_SIZE)),
        "timestep": os.environ.get("TIMESTEP", TIMESTEP),
        "sleeptime": os.environ.get("SLEEPTIME", SLEEPTIME),
        "fast_ema_period": int(os.environ.get("FAST_EMA", FAST_EMA)),
        "slow_ema_period": int(os.environ.get("SLOW_EMA", SLOW_EMA)),
        "trailing_atr_multiple": float(os.environ.get("TRAIL_ATR", TRAIL_ATR)),
    }


def run_backtest(out: Path) -> dict:
    from lumibot.backtesting import AlpacaBacktesting

    out.mkdir(parents=True, exist_ok=True)
    LOGDIR.mkdir(parents=True, exist_ok=True)
    start = TIMEZONE.localize(datetime.fromisoformat(os.environ.get("START", "2023-01-01")))
    end = TIMEZONE.localize(datetime.fromisoformat(os.environ.get("END", "2024-09-01")))

    results, _ = EmaSideTrailing.run_backtest(
        datasource_class=AlpacaBacktesting,
        backtesting_start=start,
        backtesting_end=end,
        budget=STARTING_BALANCE,
        benchmark_asset=BENCHMARK,
        minutes_before_closing=0,
        parameters=parameters(),
        show_plot=False,
        show_tearsheet=False,
        show_indicators=False,
        tearsheet_file=str(out / "tearsheet.html"),
        plot_file_html=str(out / "trades.html"),
        trades_file=str(out / "trades.csv"),
        indicators_file=str(out / "indicators.html"),
        stats_file=str(out / "stats.csv"),
        settings_file=str(out / "settings.json"),
        tearsheet_metrics_file=str(out / "metrics.json"),
        config=alpaca_config(),
        timestep=parameters()["timestep"],
        market=MARKET,
        warm_up_trading_days=EmaSideTrailing.parameters["warmup_bars"],
    )
    return results


def run_live() -> None:
    from lumibot.brokers import Alpaca

    broker = Alpaca(alpaca_config())
    if not broker.is_paper:
        raise RuntimeError("Refusing to trade: broker did not resolve to a paper account")

    strategy = EmaSideTrailing(broker=broker, parameters=parameters())
    strategy.run_live(run_once=os.environ.get("ONCE") == "true")


def main() -> None:
    mode = os.environ.get("MODE", "backtest")
    if mode == "live":
        run_live()
        return
    if mode != "backtest":
        raise ValueError(f"MODE={mode!r} is not one of 'backtest', 'live'")

    out = Path(os.environ.get("OUT", "out"))
    results = run_backtest(out)
    for name in ("cagr", "volatility", "sharpe", "max_drawdown", "total_return"):
        if name in results:
            print(f"{name}: {results[name]}")
    print(f"reports + tearsheet -> {out}/")


if __name__ == "__main__":
    main()
