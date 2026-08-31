from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from math import isfinite
from typing import Any, ClassVar, cast

from pandas import DataFrame, DatetimeIndex, Series, Timestamp

from bot.strategies.base import StrategyBase
from bot.strategies.shared import (
    TRADING_ZONE,
    Direction,
    does_macd_confirm,
    entry_quantity,
    fractional_allowed,
    latest_atr,
    next_stop,
    normalize_ohlcv,
    quantity_value,
    security_is_eligible,
)


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


def relative_volume_ready(
    frame: DataFrame,
    day: date,
    clock: time,
    multiple: float,
) -> bool:
    regular = cast(DataFrame, cast(Any, frame).between_time("09:30", "15:59"))
    index = cast(DatetimeIndex, regular.index)
    pandas_index = cast(Any, index)
    session_dates = cast(DatetimeIndex, pandas_index.normalize())
    current_session = Timestamp(day, tz=TRADING_ZONE)
    is_current = cast(Any, session_dates) == current_session
    is_earlier = cast(Any, session_dates) < current_session
    is_relevant = is_current | is_earlier
    volume = cast(Series, regular["volume"])
    cumulative_volume = cast(
        Series,
        cast(Any, volume).where(pandas_index.time <= clock, 0.0),
    )
    aggregates = DataFrame(
        {
            "session_date": session_dates,
            "daily_volume": volume,
            "cumulative_volume": cumulative_volume,
        },
        index=index,
    )
    grouped = cast(
        DataFrame,
        cast(Any, aggregates)
        .loc[is_relevant]
        .groupby("session_date", sort=True)[["daily_volume", "cumulative_volume"]]
        .sum(),
    )
    if current_session not in grouped.index:
        return False
    grouped_index = cast(Any, cast(DatetimeIndex, grouped.index))
    history = cast(DataFrame, cast(Any, grouped).loc[grouped_index < current_session].tail(20))
    if len(history) != 20:
        return False
    historical_daily_average = float(cast(Any, history["daily_volume"]).mean())
    historical_clock_average = float(cast(Any, history["cumulative_volume"]).mean())
    current_clock_volume = float(cast(Any, grouped).loc[current_session, "cumulative_volume"])
    return (
        all(
            isfinite(value)
            for value in (
                historical_daily_average,
                historical_clock_average,
                current_clock_volume,
            )
        )
        and historical_daily_average >= 1_000_000
        and current_clock_volume >= multiple * historical_clock_average
    )


class OrbStrategy(StrategyBase):
    candle_minutes: ClassVar[int]
    volume_multiple: ClassVar[float]
    uses_macd: ClassVar[bool]
    risk_fraction_max: ClassVar[float | None]
    target_multiples: ClassVar[tuple[float, float, float]]
    signal_candles_max: ClassVar[int]
    entry_extension_max: ClassVar[float | None]

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
        if equity <= self._baseline_equity * (1.0 - float(self.parameters["risk_per_day_max"])):
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

    def _filled_targets(self, pending: OrbPending, entry: float) -> tuple[float, float, float]:
        """The three scale-out levels, counted from the risk the fill actually took.

        The ten-minute register writes them as fractions of the opening range
        measured from the breakout level, which is the same 2R, 4R and 8R only
        while the fill lands on that level. A breakout candle closing well past it
        filled above targets already counted as reached, and the position scaled
        itself out within a minute of opening without the price going near the
        stop. Counting from the fill keeps every target ahead of the entry.
        """
        risk = abs(entry - pending.stop)
        return cast(
            tuple[float, float, float],
            tuple(entry + pending.direction * risk * value for value in self.target_multiples),
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
        if bars is None:
            return None
        return normalize_ohlcv(
            cast(DataFrame, bars.df),
            {"high", "low", "close", "volume"},
        )

    def _completed(self, frame: DataFrame, now: datetime) -> DataFrame:
        index = cast(DatetimeIndex, frame.index)
        mask = cast(Any, index) + timedelta(minutes=self.candle_minutes) <= now
        return cast(DataFrame, frame[mask])

    def _signal(
        self, candles: DataFrame, high: float, low: float
    ) -> tuple[int, Direction, float] | None:
        """The *first* candle since the opening range that closed outside it.

        Reading only the newest completed candle made the signal depend on which
        bars had been published when the scan ran: one arriving late was missed,
        and the breakout was then read off the candle after it — an entry a whole
        candle beyond the level the rule names.
        """
        closes = cast(Series, candles["close"])
        for position, value in enumerate(cast(list[Any], closes.tolist())):
            close = float(value)
            if not isfinite(close):
                continue
            if close > high:
                return position, 1, close
            if close < low:
                return position, -1, close
        return None

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
        index = cast(DatetimeIndex, frame.index)
        session = cast(DataFrame, frame[cast(Any, index).date == now.date()])
        session_index = cast(Any, cast(DatetimeIndex, session.index))
        opening_end = datetime.combine(now.date(), time(9, 30), TRADING_ZONE) + timedelta(
            minutes=self.candle_minutes
        )
        opening = cast(
            DataFrame,
            session[
                (session_index >= opening_end - timedelta(minutes=self.candle_minutes))
                & (session_index < opening_end)
            ],
        )
        completed = self._completed(session, now)
        if opening.empty or completed.empty:
            return
        after = cast(
            DataFrame,
            completed[cast(Any, cast(DatetimeIndex, completed.index)) >= opening_end],
        )
        if after.empty:
            return
        high = float(cast(Any, opening["high"]).max())
        low = float(cast(Any, opening["low"]).min())
        if not all(isfinite(value) for value in (high, low)):
            return
        signal = self._signal(after, high, low)
        if signal is None:
            return
        position, direction, close = signal
        self._signaled.add(key)
        # The breakout is taken at the open of the candle after the one that closed
        # outside the range. A close found further back than this engine's own bound
        # has already run, and buying it now would be a chase rather than the entry
        # the rule names.
        if len(after) - position > self.signal_candles_max:
            return
        # Both gates read the market as it stood when the signal candle closed, not
        # as it stands now: they confirm that breakout, and on a signal recovered a
        # candle late the two moments are not the same one.
        signal_at = cast(Timestamp, after.index[position])
        if not relative_volume_ready(frame, now.date(), signal_at.time(), self.volume_multiple):
            return
        if self.uses_macd:
            regular = cast(DataFrame, cast(Any, frame).between_time("09:30", "15:59"))
            history = cast(DataFrame, regular[cast(Any, regular.index) <= signal_at])
            if not does_macd_confirm(cast(Series, history["close"]), direction):
                return
        span = high - low
        stop = low + span * (0.75 if direction == 1 else 0.25)
        # The stop sits a fixed distance inside the range, so a price further past
        # the level risks more for the same setup and has already given away that
        # much of the move. Past the ceiling the breakout is left alone.
        limit = self.entry_extension_max
        if limit is not None and (
            close > high + limit * span if direction == 1 else close < low - limit * span
        ):
            return
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
            fractional_allowed(direction, bool(self.parameters["fractional_orders"])),
        )
        if quantity <= 0:
            return
        self._pending[symbol] = OrbPending(direction, stop)
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
            if frame is None:
                continue
            frame = self._completed(frame, now)
            if len(frame) < 15:
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
        size = quantity_value(
            quantity,
            fractional_allowed(holding.direction, bool(self.parameters["fractional_orders"])),
        )
        if size <= 0:
            return
        self._cancel(symbol)
        side = "sell" if holding.direction == 1 else "buy"
        self.submit_order(
            self.create_order(
                symbol,
                size,
                side,
                stop_price=round(holding.stop, 2),
                time_in_force="day",
            )
        )

    def _exit(self, symbol: str, quantity: float | None = None) -> None:
        holding = self._positions[symbol]
        amount = (
            self._quantity(symbol) if quantity is None else min(quantity, self._quantity(symbol))
        )
        if amount <= 0:
            self._positions.pop(symbol, None)
            return
        size = quantity_value(
            amount,
            fractional_allowed(holding.direction, bool(self.parameters["fractional_orders"])),
        )
        if size <= 0:
            # See the composer's _exit: a scale-out below one whole share of a
            # short is skipped rather than cancelling the stop for nothing.
            return
        self._cancel(symbol)
        side = "sell" if holding.direction == 1 else "buy"
        self.submit_order(
            self.create_order(
                symbol,
                size,
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
