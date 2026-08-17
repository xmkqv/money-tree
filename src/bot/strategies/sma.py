from datetime import date
from decimal import ROUND_DOWN, Decimal
from typing import Any, cast
from zoneinfo import ZoneInfo

from pandas import DataFrame, Series

from bot.strategies.shared import StrategyBase


LOOKBACK = 260
MIN_BARS = 205
PERIOD = 14
STOP_MULTIPLE = 1.5
MIN_NOTIONAL_USD = 1.0
SHARE_INCREMENT = Decimal("0.000000001")
TRADING_ZONE = ZoneInfo("America/New_York")


def _wilder(values: Series, period: int) -> Series:
    observed = cast(Any, values).dropna().astype(float)
    seeded = observed.copy()
    seeded.iloc[: period - 1] = float("nan")
    seeded.iloc[period - 1] = observed.iloc[:period].mean()
    return cast(Series, seeded.ewm(alpha=1.0 / period, adjust=False).mean())


def _rsi(close: Series, period: int) -> Series:
    delta = cast(Any, close).diff().dropna()
    gain = _wilder(cast(Series, delta.clip(lower=0.0)), period)
    loss = _wilder(cast(Series, (-delta).clip(lower=0.0)), period)
    return cast(Series, 100.0 - 100.0 / (1.0 + cast(Any, gain) / cast(Any, loss)))


def _true_range(high: Series, low: Series, close: Series) -> Series:
    high_values = cast(Any, high)
    low_values = cast(Any, low)
    previous = cast(Any, close).shift(1)
    high_gap = (high_values - previous).abs()
    low_gap = (low_values - previous).abs()
    widest = high_values - low_values
    widest = widest.where(widest >= high_gap, high_gap)
    return cast(Series, widest.where(widest >= low_gap, low_gap).dropna())


def _adx(high: Series, low: Series, close: Series, period: int) -> Series:
    average_range = _wilder(_true_range(high, low, close), period)
    up = cast(Any, high).diff().dropna()
    down = (-cast(Any, low).diff()).dropna()
    rising = _wilder(cast(Series, up.where((up > down) & (up > 0.0), 0.0)), period)
    falling = _wilder(cast(Series, down.where((down > up) & (down > 0.0), 0.0)), period)
    plus = 100.0 * cast(Any, rising) / cast(Any, average_range)
    minus = 100.0 * cast(Any, falling) / cast(Any, average_range)
    return _wilder(cast(Series, 100.0 * (plus - minus).abs() / (plus + minus)), period)


def _entry_quantity(
    equity: float,
    price: float,
    stop_distance: float,
    position_fraction_max: float,
    risk_per_trade_max: float,
) -> Decimal:
    if equity <= 0 or price <= 0 or stop_distance <= 0:
        return Decimal(0)
    quantity = min(
        equity * position_fraction_max / price,
        equity * risk_per_trade_max / stop_distance,
    )
    if quantity * price < MIN_NOTIONAL_USD:
        return Decimal(0)
    return Decimal(str(quantity)).quantize(SHARE_INCREMENT, rounding=ROUND_DOWN)


class Strategy(StrategyBase):
    _baseline_equity: float
    _day: date | None
    _evaluated_on: date | None
    _highest: dict[str, float]
    _locked_on: date | None
    _planned_stops: dict[str, float]

    def initialize(self) -> None:
        self.sleeptime = "1D" if self.is_backtesting else "1M"
        self._baseline_equity = 0.0
        self._day = None
        self._evaluated_on = None
        self._highest = {}
        self._locked_on = None
        self._planned_stops = {}

    def on_trading_iteration(self) -> None:
        parameters: dict[str, Any] = self.parameters
        day = self.get_datetime().astimezone(TRADING_ZONE).date()
        equity, last_equity = self._account_values()
        if day != self._day:
            self._day = day
            self._baseline_equity = last_equity if last_equity > 0 else equity
            self._evaluated_on = None
            self._locked_on = None
        if self._locked_on == day:
            return
        risk_per_day_max = float(parameters.get("risk_per_day_max", 0.02))
        if equity <= self._baseline_equity * (1.0 - risk_per_day_max):
            self._flatten(day)
            return
        if self._evaluated_on == day:
            return
        self._evaluated_on = day
        position_fraction_max = float(parameters.get("position_fraction_max", 0.20))
        risk_per_trade_max = float(parameters.get("risk_per_trade_max", 0.005))
        symbols: list[str] = parameters.get("symbols") or ["SPY"]
        for symbol in symbols:
            self._trade(symbol, equity, position_fraction_max, risk_per_trade_max)

    def on_filled_order(
        self,
        position: Any,
        order: Any,
        price: float,
        quantity: float | int,
        multiplier: float,
    ) -> None:
        symbol = str(order.asset.symbol)
        stop_price = self._planned_stops.pop(symbol, None)
        if stop_price is None or str(order.side).lower() != "buy":
            return
        stop = self.create_order(
            symbol, quantity, "sell", stop_price=stop_price, time_in_force="day"
        )
        self.submit_order(stop)

    def _account_values(self) -> tuple[float, float]:
        equity = float(self.portfolio_value)
        if self.is_backtesting:
            baseline = self._baseline_equity if self._day is not None else equity
            return equity, baseline
        account = self.broker.api.get_account()
        return float(account.portfolio_value), float(account.last_equity)

    def _cancel_symbol_orders(self, symbol: str) -> None:
        canceled = False
        for order in cast(list[Any], self.get_orders()):
            if order.is_active() and order.asset.symbol == symbol:
                self.cancel_order(order)
                canceled = True
        if canceled and not self.is_backtesting:
            self.sleep(1)

    def _flatten(self, day: date) -> None:
        self.cancel_open_orders()
        if not self.is_backtesting:
            self.sleep(1)
        for position in cast(list[Any], self.get_positions()):
            quantity = float(position.quantity)
            side = "sell" if quantity > 0 else "buy"
            order = self.create_order(position.asset, abs(quantity), side, time_in_force="day")
            self.submit_order(order)
        self._locked_on = day
        if self.exporter is not None:
            self.exporter.publish("running", "daily-loss", "warning", "Daily loss limit reached")

    def _protect(self, symbol: str, quantity: float, stop_price: float) -> None:
        self._cancel_symbol_orders(symbol)
        stop = self.create_order(
            symbol, quantity, "sell", stop_price=stop_price, time_in_force="day"
        )
        self.submit_order(stop)

    def _trade(
        self,
        symbol: str,
        equity: float,
        position_fraction_max: float,
        risk_per_trade_max: float,
    ) -> None:
        bars: Any = self.get_historical_prices(symbol, LOOKBACK, "day")
        frame: DataFrame | None = None if bars is None else bars.df
        if frame is None or len(frame) < MIN_BARS:
            return
        values = cast(Any, frame)
        high = cast(Series, values["high"])
        low = cast(Series, values["low"])
        close = cast(Series, values["close"])
        close_values = cast(Any, close)
        sma20 = close_values.rolling(20).mean()
        last = float(close_values.iloc[-1])
        trend = float(sma20.iloc[-1])
        strength = float(cast(Any, _rsi(close, PERIOD)).iloc[-1])
        average_range = float(cast(Any, _wilder(_true_range(high, low, close), PERIOD)).iloc[-1])
        position: Any = self.get_position(symbol)
        held = 0.0 if position is None else float(position.quantity)
        if held > 0:
            peak = max(self._highest.get(symbol, last), last)
            self._highest[symbol] = peak
            if last < peak - STOP_MULTIPLE * average_range or (last < trend and strength < 50.0):
                self._cancel_symbol_orders(symbol)
                self.submit_order(self.create_order(symbol, held, "sell", time_in_force="day"))
                self._highest.pop(symbol, None)
                return
            self._protect(symbol, held, round(max(0.01, peak - STOP_MULTIPLE * average_range), 2))
            return
        crossed = float(close_values.iloc[-2]) < float(sma20.iloc[-2]) and last > trend
        sma50 = float(close_values.rolling(50).mean().iloc[-1])
        sma200 = float(close_values.rolling(200).mean().iloc[-1])
        if not (crossed and last > sma50 > sma200 and 50.0 <= strength <= 70.0):
            return
        if float(cast(Any, _adx(high, low, close, PERIOD)).iloc[-1]) <= 25.0:
            return
        stop_distance = STOP_MULTIPLE * average_range
        quantity = _entry_quantity(
            equity, last, stop_distance, position_fraction_max, risk_per_trade_max
        )
        if quantity <= 0:
            return
        self._planned_stops[symbol] = round(max(0.01, last - stop_distance), 2)
        self.submit_order(self.create_order(symbol, quantity, "buy", time_in_force="day"))
        self._highest[symbol] = last
