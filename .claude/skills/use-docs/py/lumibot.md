# [lumibot][lumibot:docs]

4.6.2 · Python 3.10+ · `Strategy` lifecycle · `Trader` · backtesting data sources

```py
from datetime import datetime, timedelta

from lumibot.backtesting import AlpacaBacktesting, YahooDataBacktesting
from lumibot.brokers import Alpaca
from lumibot.entities import Asset, Order
from lumibot.strategies import Strategy
from lumibot.traders import Trader
```

[`Strategy`][lumibot:lifecycle] → subclass; the executor calls hooks in a fixed order each session.

```py
class Sample(Strategy):
    # initialize(self, parameters: dict = None); once, before the first session
    def initialize(self):
        self.sleeptime = "5M"  # int = minutes; str = "30S" | "5M" | "1H" | "1D"
        self.minutes_before_opening = 30  # before_market_opens lead
        self.minutes_before_closing = 5  # before_market_closes lead; loop stops here
        self.set_market("NYSE")  # "24/7" runs outside exchange hours
        self.symbols = self.parameters["symbols"]  # dict passed at construction
        self.vars.seen = set()  # self.vars persists via backup and restore

    def before_market_opens(self): ...  # once per session, lead minutes early
    def before_starting_trading(self): ...  # once per session, market open, before the loop

    def on_trading_iteration(self):  # every sleeptime, market hours only
        if self.first_iteration:  # True on the very first call of the run
            self.log_message("started")

    def before_market_closes(self): ...  # minutes_before_closing before the close
    def after_market_closes(self): ...  # after the last iteration
    def on_strategy_end(self): ...  # backtest finish

    def on_abrupt_closing(self): ...  # trader stopped (SIGINT or stop_all)
    def on_bot_crash(self, error: Exception):  # default calls on_abrupt_closing
        self.log_message(repr(error), color="red")  # live loop continues afterwards

    # dict of stats logged after each iteration; locals of the iteration in context
    def trace_stats(self, context: dict, snapshot_before: dict) -> dict:
        return {"cash": self.get_cash()}
```

[`create_order(asset, quantity, side, ...)`][lumibot:orders] → `Order`; nothing is sent until `submit_order`.

```py
def enter(self, symbol: str, quantity: str, stop: float, limit: float):
    # asset: str | Asset; quantity: int | str | Decimal (float is deprecated)
    market = self.create_order(symbol, quantity, "buy", time_in_force="day")
    resting = self.create_order(symbol, quantity, "sell", stop_price=stop, time_in_force="gtc")
    limited = self.create_order(symbol, quantity, "buy", limit_price=limit)
    trailing = self.create_order(symbol, quantity, "sell", trail_percent=0.05)  # 5%
    tagged = Order(  # tag is an Order argument; create_order has no tag parameter
        self, symbol, quantity, Order.OrderSide.BUY, tag="entry-a",
        custom_params={"client_order_id": "entry-a"},  # passed through to the broker
    )
    self.submit_order(market)  # Order | list[Order]
    self.submit_orders([resting, limited])  # batch form
```

[`order_class`][lumibot:orders] selects `Order.OrderClass.{SIMPLE, BRACKET, OCO, OTO, MULTILEG}`.

```py
def protected_entry(self, symbol: str, quantity: int, entry: float, target: float, stop: float):
    bracket = self.create_order(  # entry plus profit exit plus loss exit
        symbol, quantity, "buy",
        limit_price=entry,
        secondary_limit_price=target,
        secondary_stop_price=stop,
        secondary_stop_limit_price=stop * 0.995,  # optional stop-limit modifier
        order_class=Order.OrderClass.BRACKET,
    )
    oto = self.create_order(  # entry plus one exit
        symbol, quantity, "buy",
        limit_price=entry, secondary_stop_price=stop,
        order_class=Order.OrderClass.OTO,
    )
    oco = self.create_order(  # exits only, for an existing position
        symbol, quantity, "sell",
        limit_price=target, stop_price=stop,
        order_class=Order.OrderClass.OCO,
    )
    self.submit_order(bracket)
    return bracket.child_orders  # populated as the broker reports children
```

[`on_filled_order(position, order, price, quantity, multiplier)`][lumibot:on_filled_order] → order events arrive as callbacks.

```py
def on_new_order(self, order: Order): ...  # broker accepted the order
def on_canceled_order(self, order: Order): ...

def on_partially_filled_order(self, position, order, price, quantity, multiplier):
    self.log_message(f"{order.asset.symbol} partial {quantity} @ {price}")

def on_filled_order(self, position, order, price, quantity, multiplier):
    # price and quantity describe this fill; position is the resulting Position
    if order.is_filled() and order.is_buy_order():
        self.log_message(f"avg {order.get_fill_price()} status={order.status}")
    for child in order.child_orders:  # advanced-order legs
        self.log_message(f"{child.order_type} active={child.is_active()}")
```

[`get_positions()`][lumibot:positions] / [`get_orders(statuses=...)`][lumibot:orders] → tracked broker state.

```py
def inspect(self, symbol: str):
    position = self.get_position(symbol)  # Position | None
    held = 0.0 if position is None else float(position.quantity)  # negative = short
    holdings = {p.asset: float(p.quantity) for p in self.get_positions()}  # cash excluded

    active = self.get_orders(statuses=Order.ACTIVE_STATUSES)  # list[Order]
    mine = [o for o in active if o.asset == Asset(symbol=symbol, asset_type="stock")]
    order = self.get_order(mine[0].identifier) if mine else None  # fresh single lookup

    self.cancel_order(order) if order else None
    self.cancel_open_orders()  # this strategy only; or pass an already fetched list
    self.sell_all(cancel_open_orders=True)  # market-close every position
    return held, holdings, self.get_portfolio_value(), self.get_cash()
```

[`get_historical_prices(asset, length, timestep, timeshift)`][lumibot:get_historical_prices] → `Bars`.

```py
def prices(self, symbol: str):
    quote = self.get_last_price(symbol)  # float | Decimal | None
    batch = self.get_last_prices(["SPY", "QQQ"])  # {symbol: price} for str, {Asset: price} for Asset
    bars = self.get_historical_prices(symbol, 50, "5min")  # "minute"|"day"|"15m"|"1h"|"2 days"
    if bars is None:
        return None
    frame = bars.pandas_df  # columns open high low close volume; tz-aware index
    prior = self.get_historical_prices(symbol, 20, "day", timeshift=1)  # int = bars back
    hourly_ago = self.get_historical_prices(symbol, 5, "minute", timeshift=timedelta(hours=1))
    many = self.get_historical_prices_for_assets(["SPY", "QQQ"], 20, "day")  # {asset: Bars}
    now = self.get_datetime()  # aware; backtest clock or wall clock
    return frame, quote, batch, prior, many, now, self.get_round_minute()
```

[`Trader`][lumibot:alpaca] → runs strategies against a broker until stopped.

```py
config = {"API_KEY": "...", "API_SECRET": "...", "PAPER": True, "MARKET": "NYSE"}
broker = Alpaca(config)  # PAPER False = live account

strategy = Sample(broker=broker, parameters={"symbols": ["SPY"]}, name="sample")
trader = Trader(logfile="", quiet_logs=False)
trader.add_strategy(strategy)
try:
    trader.run_all()  # blocks; installs a SIGINT handler
finally:
    trader.stop_all()  # from another thread or a SIGTERM handler to stop the run
```

[`Strategy.backtest(datasource_class, start, end, ...)`][lumibot:backtesting] → stats `dict`.

```py
results = Sample.backtest(
    YahooDataBacktesting,  # or AlpacaBacktesting with config=... and timestep="minute"
    datetime(2023, 1, 1),  # naive values are localized to the default timezone
    datetime(2024, 1, 1),
    parameters={"symbols": ["SPY"]},
    budget=100_000.0,
    benchmark_asset="SPY",
    show_plot=False,
    show_tearsheet=False,
    show_indicators=False,
    save_tearsheet=False,
    show_progress_bar=False,
    quiet_logs=True,
    stats_file="out/stats.csv",
    trades_file="out/trades.csv",
    plot_file_html="out/plot.html",
    indicators_file="out/indicators.html",
    settings_file="out/settings.json",
)
# results keys come from stats_summary: cagr, volatility, sharpe, max_drawdown, romad, total_return
results, strategy = Sample(broker, ...).run_backtest(...)  # lower level; returns a tuple
```

[`log_message`, `add_marker`, `add_line`][lumibot:backtest-indicators] → plots written to `indicators_file` after a backtest.

```py
def annotate(self, symbol: str, price: float, stop: float):
    self.log_message(f"{symbol} at {price}", color="blue")  # color: str; broadcast: bool
    self.logger.info("plain logger")  # stdlib logger
    self.add_marker(
        "entry", price, color="green", symbol="arrow-up", size=12,
        detail_text="reason", dt=self.get_datetime(), plot_name="default_plot",
    )
    self.add_line("stop", stop, color="red", style="dashed", width=1)  # one point per call
```

## refs

[lumibot:docs]: https://lumibot.lumiwealth.com/

[lumibot:lifecycle]: https://lumibot.lumiwealth.com/lifecycle_methods.html

[lumibot:on_filled_order]: https://lumibot.lumiwealth.com/lifecycle_methods.on_filled_order.html

[lumibot:properties]: https://lumibot.lumiwealth.com/strategy_properties.html
    You can set the sleep time as an integer which will be interpreted as minutes.

[lumibot:orders]: https://lumibot.lumiwealth.com/strategy_methods.orders.html
    In live trading this refreshes broker order state before returning by default.

[lumibot:create_order]: https://lumibot.lumiwealth.com/strategy_methods.orders/lumibot.strategies.strategy.Strategy.create_order.html

[lumibot:positions]: https://lumibot.lumiwealth.com/entities.position.html

[lumibot:get_historical_prices]: https://lumibot.lumiwealth.com/strategy_methods.data/lumibot.strategies.strategy.Strategy.get_historical_prices.html
    Passing an `int` shifts by bars (positive = past, negative = future).

[lumibot:alpaca]: https://lumibot.lumiwealth.com/brokers.alpaca.html
    Stock trading is limited to market hours; crypto trading is 24/7

[lumibot:backtesting]: https://lumibot.lumiwealth.com/backtesting.how_to_backtest.html

[lumibot:backtest-indicators]: https://lumibot.lumiwealth.com/backtesting.indicators_files.html

[lumibot:asset]: https://lumibot.lumiwealth.com/entities.asset.html

[lumibot:release]: https://pypi.org/project/lumibot/4.6.2/
