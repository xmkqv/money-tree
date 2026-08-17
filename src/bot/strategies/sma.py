from math import floor
from typing import Any

from bot.strategies.shared import StrategyBase


type Series = Any

LOOKBACK = 260
MIN_BARS = 205
PERIOD = 14
STOP_MULTIPLE = 1.5


def _wilder(values: Series, period: int) -> Series:
    observed: Series = values.dropna().astype(float)
    seeded: Series = observed.copy()
    seeded.iloc[: period - 1] = float("nan")
    seeded.iloc[period - 1] = observed.iloc[:period].mean()
    return seeded.ewm(alpha=1.0 / period, adjust=False).mean()


def _rsi(close: Series, period: int) -> Series:
    delta: Series = close.diff().dropna()
    gain: Series = _wilder(delta.clip(lower=0.0), period)
    loss: Series = _wilder((-delta).clip(lower=0.0), period)
    return 100.0 - 100.0 / (1.0 + gain / loss)


def _true_range(high: Series, low: Series, close: Series) -> Series:
    previous: Series = close.shift(1)
    high_gap: Series = (high - previous).abs()
    low_gap: Series = (low - previous).abs()
    widest: Series = high - low
    widest = widest.where(widest >= high_gap, high_gap)
    return widest.where(widest >= low_gap, low_gap).dropna()


def _adx(high: Series, low: Series, close: Series, period: int) -> Series:
    average_range: Series = _wilder(_true_range(high, low, close), period)
    up: Series = high.diff().dropna()
    down: Series = (-low.diff()).dropna()
    rising: Series = _wilder(up.where((up > down) & (up > 0.0), 0.0), period)
    falling: Series = _wilder(down.where((down > up) & (down > 0.0), 0.0), period)
    plus: Series = 100.0 * rising / average_range
    minus: Series = 100.0 * falling / average_range
    return _wilder(100.0 * (plus - minus).abs() / (plus + minus), period)


class Strategy(StrategyBase):
    _highest: dict[str, float]

    def initialize(self) -> None:
        self.sleeptime = "1D"
        self._highest = {}

    def on_trading_iteration(self) -> None:
        parameters: dict[str, Any] = self.parameters
        symbols: list[str] = parameters.get("symbols") or ["SPY"]
        fraction = float(parameters.get("position_fraction", 0.10))
        for symbol in symbols:
            self._trade(symbol, fraction)

    def _trade(self, symbol: str, fraction: float) -> None:
        bars: Any = self.get_historical_prices(symbol, LOOKBACK, "day")
        frame: Series = None if bars is None else bars.df
        if frame is None or len(frame) < MIN_BARS:
            return
        high: Series = frame["high"]
        low: Series = frame["low"]
        close: Series = frame["close"]
        sma20: Series = close.rolling(20).mean()
        last = float(close.iloc[-1])
        trend = float(sma20.iloc[-1])
        strength = float(_rsi(close, PERIOD).iloc[-1])
        position: Any = self.get_position(symbol)
        held = 0 if position is None else int(position.quantity)
        if held > 0:
            peak = max(self._highest.get(symbol, last), last)
            self._highest[symbol] = peak
            average_range = float(_wilder(_true_range(high, low, close), PERIOD).iloc[-1])
            if last < peak - STOP_MULTIPLE * average_range or (last < trend and strength < 50.0):
                self.submit_order(self.create_order(symbol, held, "sell"))
                self._highest.pop(symbol, None)
            return
        crossed = float(close.iloc[-2]) < float(sma20.iloc[-2]) and last > trend
        sma50 = float(close.rolling(50).mean().iloc[-1])
        sma200 = float(close.rolling(200).mean().iloc[-1])
        if not (crossed and last > sma50 > sma200 and 50.0 <= strength <= 70.0):
            return
        if float(_adx(high, low, close, PERIOD).iloc[-1]) <= 25.0:
            return
        quantity = floor(fraction * float(self.portfolio_value) / last)
        if quantity > 0:
            self.submit_order(self.create_order(symbol, quantity, "buy"))
            self._highest[symbol] = last
