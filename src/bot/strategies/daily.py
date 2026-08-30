from datetime import date
from typing import Any, ClassVar, cast

from pandas import DataFrame, DatetimeIndex

from bot.strategies.base import StrategyBase
from bot.strategies.shared import (
    TRADING_ZONE,
    earnings_blocked,
    earnings_exit_due,
    entry_quantity,
    latest_atr,
    market_is_rising,
    normalize_ohlcv,
    signal_exit,
)


LOOKBACK = 260


class DailyStrategy(StrategyBase):
    stop_multiple: ClassVar[float]
    blocks_entries_before_earnings: ClassVar[bool]
    caps_risk_per_trade: ClassVar[bool]

    _baseline_equity: float
    _day: date | None
    _evaluated_on: date | None
    _highest: dict[str, float]
    _locked_on: date | None
    _stops: dict[str, float]

    def initialize(self) -> None:
        self.sleeptime = "1D" if self.is_backtesting else "1M"
        self._baseline_equity = 0.0
        self._day = None
        self._evaluated_on = None
        self._highest = {}
        self._locked_on = None
        self._stops = {}

    def on_trading_iteration(self) -> None:
        parameters: dict[str, Any] = self.parameters
        day = self.get_datetime().date()
        equity, last_equity = self._account_values()
        if day != self._day:
            self._day = day
            self._baseline_equity = last_equity if last_equity > 0 else equity
            self._evaluated_on = None
            self._locked_on = None
        if self._locked_on == day:
            return
        if equity <= self._baseline_equity * (1.0 - float(parameters["risk_per_day_max"])):
            self._flatten(day)
            return
        if self._evaluated_on == day:
            return
        self._evaluated_on = day
        market = self._frame("^GSPC", 30)
        if market is None or not market_is_rising(market):
            return
        symbols: list[str] = parameters.get("symbols") or ["SPY"]
        for symbol in symbols:
            self._trade(symbol, day, equity)

    def _entry_ready(self, frame: DataFrame) -> bool:
        raise NotImplementedError

    def _account_values(self) -> tuple[float, float]:
        equity = float(self.portfolio_value)
        if self.is_backtesting:
            baseline = self._baseline_equity if self._day is not None else equity
            return equity, baseline
        account = self.broker.api.get_account()
        return float(account.portfolio_value), float(account.last_equity)

    def _cancel_symbol_orders(self, symbol: str) -> None:
        orders = [
            order
            for order in cast(list[Any], self.get_orders())
            if order.is_active() and str(order.asset.symbol) == symbol
        ]
        self.cancel_open_orders(orders)
        if orders and not self.is_backtesting:
            self.sleep(1)

    def _earnings_exit_due(self, symbol: str, day: date) -> bool:
        """Whether earnings force an exit, ignoring a calendar that cannot be read."""
        try:
            return earnings_exit_due(symbol, day)
        except Exception:
            return False

    def _flatten(self, day: date) -> None:
        self.sell_all()
        self._locked_on = day
        if self.exporter is not None:
            self.exporter.publish("running", "daily-loss", "warning", "Daily loss limit reached")

    def _frame(self, symbol: str, length: int = LOOKBACK) -> DataFrame | None:
        bars: Any = self.get_historical_prices(symbol, length, "day")
        if bars is None:
            return None
        frame = normalize_ohlcv(cast(DataFrame, bars.df), {"high", "low", "close"})
        day = self.get_datetime().astimezone(TRADING_ZONE).date()
        index = cast(Any, cast(DatetimeIndex, frame.index))
        return cast(DataFrame, frame[index.date < day])

    def _trade(self, symbol: str, day: date, equity: float) -> None:
        frame = self._frame(symbol)
        if frame is None:
            return
        position: Any = self.get_position(symbol)
        held = 0.0 if position is None else float(position.quantity)
        if held > 0:
            self._manage(symbol, day, held, frame)
            return
        if not self._entry_ready(frame):
            return
        if self.blocks_entries_before_earnings and earnings_blocked(symbol, day):
            return
        average_range = latest_atr(frame)
        price = float(cast(Any, frame["close"]).iloc[-1])
        stop_distance = self.stop_multiple * average_range
        parameters: dict[str, Any] = self.parameters
        risk_limit = float(parameters["risk_per_trade_max"]) if self.caps_risk_per_trade else None
        quantity = entry_quantity(
            equity,
            price,
            stop_distance,
            min(0.10, float(parameters["position_fraction_max"])),
            risk_limit,
            bool(parameters["fractional_orders"]),
        )
        if quantity <= 0:
            return
        self._highest[symbol] = price
        self._stops[symbol] = price - stop_distance
        self.submit_order(self.create_order(symbol, quantity, "buy", time_in_force="day"))

    def _manage(self, symbol: str, day: date, held: float, frame: DataFrame) -> None:
        last = float(cast(Any, frame["close"]).iloc[-1])
        highest = max(self._highest.get(symbol, last), last)
        self._highest[symbol] = highest
        stop = max(self._stops.get(symbol, 0.0), highest - self.stop_multiple * latest_atr(frame))
        self._stops[symbol] = stop
        if last >= stop and not signal_exit(frame) and not self._earnings_exit_due(symbol, day):
            return
        self._cancel_symbol_orders(symbol)
        self.submit_order(self.create_order(symbol, held, "sell", time_in_force="day"))
        self._highest.pop(symbol, None)
        self._stops.pop(symbol, None)
