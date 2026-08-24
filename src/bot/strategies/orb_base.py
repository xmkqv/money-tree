from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, ClassVar, cast
from zoneinfo import ZoneInfo

from lumibot.constants import LUMIBOT_DEFAULT_TIMEZONE
from pandas import DataFrame

from bot.strategies.base import StrategyBase
from bot.strategies.shared import (
    Direction,
    does_macd_confirm,
    entry_quantity,
    latest_atr,
    next_stop,
    quantity_value,
    security_is_eligible,
)


TRADING_ZONE = ZoneInfo(LUMIBOT_DEFAULT_TIMEZONE)


@dataclass(slots=True)
class OrbPosition:
    direction: Direction
    entry: float
    stop: float
    original_quantity: float
    highest: float
    lowest: float
    targets: tuple[float, float, float]
    stage: int = 0


@dataclass(slots=True)
class OrbPending:
    direction: Direction
    stop: float
    targets: tuple[float, float, float]


def trading_frame(frame: DataFrame) -> DataFrame:
    values = frame.copy()
    if values.empty:
        return values
    index = cast(Any, values.index)
    if index.tz is None:
        index = index.tz_localize(UTC)
    values.index = index.tz_convert(TRADING_ZONE)
    return values.sort_index()


def relative_volume_ready(
    frame: DataFrame,
    day: date,
    clock: time,
    multiple: float,
) -> bool:
    regular = cast(Any, trading_frame(frame)).between_time("09:30", "15:59")
    current = regular[regular.index.date == day]
    history = regular[regular.index.date < day]
    totals = [
        float(group[group.index.time <= clock]["volume"].sum())
        for _, group in history.groupby(history.index.date)
    ][-20:]
    daily = [
        float(group["volume"].sum())
        for _, group in history.groupby(history.index.date)
    ][-20:]
    return (
        len(totals) == 20
        and len(daily) == 20
        and sum(daily) / len(daily) >= 1_000_000
        and float(current["volume"].sum()) >= multiple * sum(totals) / len(totals)
    )


class OrbStrategy(StrategyBase):
    candle_minutes: ClassVar[int]
    volume_multiple: ClassVar[float]
    uses_macd: ClassVar[bool]
    risk_fraction_max: ClassVar[float | None]

    _baseline_equity: float
    _day: date | None
    _exit_pending: set[str]
    _locked_on: date | None
    _pending: dict[str, OrbPending]
    _positions: dict[str, OrbPosition]
    _signaled: set[tuple[date, str]]

    def initialize(self) -> None:
        self.sleeptime = "1M"
        self._baseline_equity = 0.0
        self._day = None
        self._exit_pending = set()
        self._locked_on = None
        self._pending = {}
        self._positions = {}
        self._signaled = set()

    def on_trading_iteration(self) -> None:
        now = self.get_datetime().astimezone(TRADING_ZONE)
        equity, last_equity = self._account_values()
        if now.date() != self._day:
            self._day = now.date()
            self._baseline_equity = last_equity if last_equity > 0 else equity
            self._locked_on = None
        if self._locked_on == now.date():
            return
        if equity <= self._baseline_equity * (
            1.0 - float(self.parameters["risk_per_day_max"])
        ):
            self._flatten(now.date())
            return
        self._manage(now)
        start = time(9, 30) if self.candle_minutes == 5 else time(9, 40)
        if not start <= now.time() <= time(10, 30) or now.minute % self.candle_minutes:
            return
        symbols: list[str] = self.parameters.get("symbols") or ["SPY"]
        for symbol in symbols:
            self._scan(symbol, now, equity)

    def on_filled_order(
        self,
        position: Any,
        order: Any,
        price: float,
        quantity: float | int,
        multiplier: float,
    ) -> None:
        symbol = str(order.asset.symbol)
        pending = self._pending.pop(symbol, None)
        if pending is not None:
            targets = self._filled_targets(pending, float(price))
            self._positions[symbol] = OrbPosition(
                pending.direction,
                float(price),
                pending.stop,
                abs(float(quantity)),
                float(price),
                float(price),
                targets,
            )
            self._protect(symbol)
            return
        if symbol not in self._exit_pending:
            return
        self._exit_pending.discard(symbol)
        remaining = abs(float(getattr(position, "quantity", 0.0)))
        if remaining <= 0:
            self._positions.pop(symbol, None)
        else:
            self._protect(symbol)

    def _filled_targets(
        self, pending: OrbPending, entry: float
    ) -> tuple[float, float, float]:
        if self.candle_minutes == 10:
            return pending.targets
        risk = abs(entry - pending.stop)
        return cast(
            tuple[float, float, float],
            tuple(entry + pending.direction * risk * value for value in (1.5, 2.5, 4.0)),
        )

    def _account_values(self) -> tuple[float, float]:
        equity = float(self.portfolio_value)
        if self.is_backtesting:
            baseline = self._baseline_equity if self._day is not None else equity
            return equity, baseline
        account = self.broker.api.get_account()
        return float(account.portfolio_value), float(account.last_equity)

    def _frame(self, symbol: str, length: int = 2200) -> DataFrame | None:
        bars: Any = self.get_historical_prices(
            symbol,
            length,
            f"{self.candle_minutes}min",
            include_after_hours=False,
        )
        return None if bars is None else trading_frame(bars.df)

    def _scan(self, symbol: str, now: datetime, equity: float) -> None:
        key = (now.date(), symbol)
        if (
            key in self._signaled
            or symbol in self._pending
            or self.get_position(symbol) is not None
        ):
            return
        if not security_is_eligible(symbol):
            return
        frame = self._frame(symbol)
        if frame is None:
            return
        values = cast(Any, frame)
        session = values[values.index.date == now.date()]
        opening_end = datetime.combine(
            now.date(), time(9, 30), TRADING_ZONE
        ) + timedelta(minutes=self.candle_minutes)
        opening = session[
            (session.index >= opening_end - timedelta(minutes=self.candle_minutes))
            & (session.index < opening_end)
        ]
        completed = session[session.index + timedelta(minutes=self.candle_minutes) <= now]
        if opening.empty or completed.empty or completed.index[-1] < opening_end:
            return
        last = completed.iloc[-1]
        high = float(opening["high"].max())
        low = float(opening["low"].min())
        close = float(last["close"])
        direction: Direction | None = 1 if close > high else -1 if close < low else None
        if direction is None:
            return
        self._signaled.add(key)
        clock = completed.index[-1].time()
        if not relative_volume_ready(frame, now.date(), clock, self.volume_multiple):
            return
        if self.uses_macd:
            regular = cast(Any, trading_frame(frame)).between_time("09:30", "15:59")
            history = regular[regular.index <= completed.index[-1]]
            if not does_macd_confirm(history["close"], direction):
                return
        span = high - low
        stop = low + span * (0.75 if direction == 1 else 0.25)
        if direction == 1:
            targets = (high + 0.5 * span, high + span, high + 2.0 * span)
        else:
            targets = (low - 0.5 * span, low - span, low - 2.0 * span)
        stop_distance = abs(close - stop)
        risk_limit = float(self.parameters["risk_per_trade_max"])
        if self.risk_fraction_max is not None:
            risk_limit = min(risk_limit, self.risk_fraction_max)
        quantity = entry_quantity(
            equity,
            close,
            stop_distance,
            min(0.10, float(self.parameters["position_fraction_max"])),
            risk_limit,
            bool(self.parameters["fractional_orders"]),
        )
        if quantity <= 0:
            return
        self._pending[symbol] = OrbPending(direction, stop, targets)
        side = "buy" if direction == 1 else "sell"
        self.submit_order(self.create_order(symbol, quantity, side, time_in_force="day"))

    def _manage(self, now: datetime) -> None:
        for symbol, holding in list(self._positions.items()):
            if symbol in self._exit_pending:
                continue
            if now.time() >= time(15, 55):
                self._exit(symbol)
                continue
            price = float(self.get_last_price(symbol))
            holding.highest = max(holding.highest, price)
            holding.lowest = min(holding.lowest, price)
            reached = (
                price >= holding.targets[holding.stage]
                if holding.direction == 1
                else price <= holding.targets[holding.stage]
            )
            if reached:
                if holding.stage == 0:
                    quantity = holding.original_quantity * 0.5
                elif holding.stage == 1:
                    quantity = holding.original_quantity * 0.25
                else:
                    self._exit(symbol)
                    continue
                holding.stage += 1
                self._exit(symbol, quantity)
                continue
            if holding.stage == 0:
                continue
            frame = self._frame(symbol, 40)
            if frame is None or len(frame) < 15:
                continue
            trail = 1.5 * latest_atr(frame)
            candidate = (
                max(holding.entry, holding.highest - trail)
                if holding.direction == 1
                else min(holding.entry, holding.lowest + trail)
            )
            holding.stop = next_stop(holding.direction, holding.stop, candidate)
            self._protect(symbol)

    def _protect(self, symbol: str) -> None:
        holding = self._positions[symbol]
        quantity = self._quantity(symbol)
        if quantity <= 0:
            return
        self._cancel(symbol)
        side = "sell" if holding.direction == 1 else "buy"
        self.submit_order(
            self.create_order(
                symbol,
                quantity_value(quantity, bool(self.parameters["fractional_orders"])),
                side,
                stop_price=round(holding.stop, 2),
                time_in_force="day",
            )
        )

    def _exit(self, symbol: str, quantity: float | None = None) -> None:
        holding = self._positions[symbol]
        amount = (
            self._quantity(symbol)
            if quantity is None
            else min(quantity, self._quantity(symbol))
        )
        if amount <= 0:
            self._positions.pop(symbol, None)
            return
        self._cancel(symbol)
        side = "sell" if holding.direction == 1 else "buy"
        self.submit_order(
            self.create_order(
                symbol,
                quantity_value(amount, bool(self.parameters["fractional_orders"])),
                side,
                time_in_force="day",
            )
        )
        self._exit_pending.add(symbol)

    def _cancel(self, symbol: str) -> None:
        orders = [
            order
            for order in cast(list[Any], self.get_orders())
            if order.is_active() and str(order.asset.symbol) == symbol
        ]
        self.cancel_open_orders(orders)
        if orders and not self.is_backtesting:
            self.sleep(1)

    def _quantity(self, symbol: str) -> float:
        position: Any = self.get_position(symbol)
        return 0.0 if position is None else abs(float(position.quantity))

    def _flatten(self, day: date) -> None:
        self.sell_all()
        self._locked_on = day
        if self.exporter is not None:
            self.exporter.publish("running", "daily-loss", "warning", "Daily loss limit reached")
