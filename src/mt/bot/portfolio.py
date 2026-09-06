from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from math import isfinite
from typing import Any, cast

from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from lumibot.strategies import Strategy as LumibotStrategy
from pandas import DataFrame, DatetimeIndex

from mt.config.settings import settings
from mt.data.live import BrokerLive, EngineLive, Live
from mt.data.past import MARKET_SYMBOL, Past
from mt.data.universe import eligible
from mt.exchange import TRADING_ZONE, session_bounds
from mt.position import Direction, entry_quantity, is_fractional_allowed, quantity_value, round_stop
from mt.snapshot import EventLevel
from mt.strategies.base import Candidate, Holding, Session, Strategy
from mt.strategies.keys import StrategyName, is_strategy_name
from mt.strategies.order_tag import find_order_tag, order_tag
from mt.strategies.registry import STRATEGIES

from .export import StateExporter


@dataclass(slots=True)
class Pending:
    holding: Holding
    submitted_at: datetime
    notional: float


STOP_COVERAGE_DRIFT_MAX = 1e-6


class Portfolio(LumibotStrategy):
    exporter: StateExporter | None = None

    def on_bot_crash(self, error: Exception) -> None:
        if self.exporter is not None:
            self.exporter.publish("failed", "crash", "error", type(error).__name__)

    def on_abrupt_closing(self) -> None:
        if self.exporter is not None:
            self.exporter.close("stopped", "Trading run stopped")

    def on_strategy_end(self) -> None:
        self.on_abrupt_closing()

    def initialize(self) -> None:
        self.sleeptime = "1M"
        self.minutes_before_opening = 30
        supplied = cast(list[str], self.parameters["strategies"])
        selected: list[StrategyName] = [value for value in supplied if is_strategy_name(value)]
        if len(selected) != len(supplied):
            raise ValueError("strategies parameter contains unknown strategy names")
        given = cast(list[str] | None, self.parameters.get("symbols"))
        if self.is_backtesting and not given:
            raise ValueError("a replay needs its symbols")
        self.live: Live = EngineLive(given) if given else BrokerLive()
        self.past = Past()
        self._given = given
        self._selected = set(selected)
        self._strategies = {cls.key: cls(self) for cls in STRATEGIES}
        self._holdings: dict[str, Holding] = {}
        self._pending: dict[str, Pending] = {}
        self._claims: dict[str, StrategyName | None] = {}
        self._stops: dict[str, tuple[float, float]] = {}
        self._closing: set[str] = set()
        self._events: set[str] = set()
        self._traded: dict[str, set[tuple[date, str]]] = {cls.family: set() for cls in STRATEGIES}
        self._day: date | None = None
        self._baseline_equity = 0.0
        self._locked_on: date | None = None
        self._daily_frames: dict[str, DataFrame] = {}
        self._eligible_symbols: list[str] = []
        self._prepared_on: date | None = None
        self._preparation_attempts = 0
        self._preparation_attempts_on: date | None = None
        self._restored = False

    def before_market_opens(self) -> None:
        self._restore()
        self._prepare(self.get_datetime().astimezone(TRADING_ZONE))

    def on_trading_iteration(self) -> None:
        now = self.get_datetime().astimezone(TRADING_ZONE)
        bounds = session_bounds(now.date())
        if bounds is None:
            return
        opens, closes = bounds
        session = Session(now, opens, closes)
        self._restore()
        self._begin_day(now.date())
        self._reconcile(now)
        if self._is_daily_loss_reached(now.date()):
            return
        self._prepare(now)
        for holding in list(self._holdings.values()):
            holding.strategy.manage(holding, session)
        for strategy in self._strategies.values():
            if self._is_runnable(strategy):
                strategy.run(session)

    def before_market_closes(self) -> None:
        for holding in list(self._holdings.values()):
            if holding.strategy.is_stop_resting:
                self.exit(holding)

    def on_filled_order(
        self,
        position: Any,
        order: Any,
        price: float,
        quantity: float | int,
        multiplier: float,
    ) -> None:
        symbol = str(order.asset.symbol)
        side = str(order.side).lower()
        pending = self._pending.get(symbol)
        entry_side = "buy" if pending is None or pending.holding.direction == 1 else "sell"
        if pending is not None and entry_side in side:
            self._pending.pop(symbol)
            holding = pending.holding
            holding.entry = self._entry_price(order, price)
            holding.risk = abs(holding.entry - holding.stop)
            holding.highest = holding.entry
            holding.lowest = holding.entry
            original = max(self._quantity(symbol), abs(float(quantity)))
            holding.ladder = holding.strategy.ladder(holding, original, original)
            self._holdings[symbol] = holding
            if holding.strategy.is_stop_resting:
                self.protect(holding)
            return
        self._closing.discard(symbol)
        remaining = abs(float(getattr(position, "quantity", 0.0)))
        if remaining <= 0:
            self._release(symbol)
        elif symbol in self._holdings:
            holding = self._holdings[symbol]
            ladder = holding.ladder
            if ladder is not None and ladder.stage == 0:
                ladder.original_quantity = max(ladder.original_quantity, remaining)
            self.protect(holding, remaining)

    def eligible_symbols(self) -> list[str]:
        return self._eligible_symbols

    def daily_frame(self, symbol: str, now: datetime) -> DataFrame | None:
        frame = self._daily_frames.get(symbol)
        return None if frame is None else self._completed(frame, now)

    def market_frame(self, now: datetime) -> DataFrame | None:
        return self.daily_frame(MARKET_SYMBOL, now)

    def minute_frames(
        self, symbols: list[str], start: datetime, now: datetime, minutes: int
    ) -> dict[str, DataFrame]:
        timeframe = TimeFrame(minutes, cast(TimeFrameUnit, TimeFrameUnit.Minute))
        frames = self.past.bars(symbols, timeframe, start, now, settings.past.intraday_feed)
        return {symbol: self._completed(frame, now, minutes) for symbol, frame in frames.items()}

    def last_price(self, symbol: str) -> float:
        return float(self.get_last_price(symbol))

    def position_count(self, keys: frozenset[StrategyName]) -> int:
        held = sum(1 for holding in self._holdings.values() if holding.strategy.key in keys)
        ordered = sum(
            1
            for symbol, pending in self._pending.items()
            if pending.holding.strategy.key in keys and symbol not in self._holdings
        )
        return held + ordered

    def is_taken(self, strategy: Strategy, symbol: str, day: date) -> bool:
        return self._is_claimed(symbol) or (day, symbol) in self._traded[strategy.family]

    def record(self, strategy: Strategy, key: str, level: EventLevel, message: str) -> None:
        self._record(f"{strategy.key}.{key}", level, message, strategy.key)

    def _is_runnable(self, strategy: Strategy) -> bool:
        return strategy.key in self._selected and not strategy.is_paused

    def _entry_price(self, order: Any, price: float) -> float:
        average = getattr(order, "avg_fill_price", None)
        value = 0.0 if average is None else float(average)
        return value if isfinite(value) and value > 0 else float(price)

    def _record(
        self,
        key: str,
        level: EventLevel,
        message: str,
        strategy: StrategyName | None = None,
    ) -> None:
        if key in self._events:
            return
        self._events.add(key)
        if self.exporter is not None:
            self.exporter.publish("running", key, level, message, strategy=strategy)

    def _equity(self) -> float:
        value = self.get_portfolio_value()
        if value is None:
            raise RuntimeError("portfolio value is unavailable")
        return float(value)

    def _begin_day(self, day: date) -> None:
        if day == self._day:
            return
        self._day = day
        self._baseline_equity = self._equity()
        self._events.clear()
        for strategy in self._strategies.values():
            strategy.begin(day)

    def _is_daily_loss_reached(self, day: date) -> bool:
        if self._locked_on == day:
            return True
        limit = settings.risk.per_day_max
        if self._equity() > self._baseline_equity * (1.0 - limit):
            return False
        self.cancel_open_orders()
        for holding in list(self._holdings.values()):
            self.exit(holding)
        self._locked_on = day
        self._record("day.loss_reached", "warning", "Daily loss limit reached")
        return True

    def _restore(self) -> None:
        if self._restored:
            return
        for strategy in self._strategies.values():
            if strategy.key in self._selected and strategy.is_paused:
                self._record(
                    f"strategy.paused.{strategy.key}",
                    "warning",
                    f"{strategy.name()} is paused: existing positions only, no new entries",
                    strategy.key,
                )
        self._record(
            "feed.announced",
            "info",
            f"Intraday candles read the Alpaca {settings.past.intraday_feed} feed",
        )
        positions = cast(list[Any], self.live.positions())
        self._restored = True
        symbols = sorted({str(position.symbol) for position in positions})
        if not symbols:
            return
        orders = cast(list[Any], self.live.tagged_orders(symbols))
        tagged = [
            (order, tag)
            for order in orders
            if (tag := find_order_tag(str(order.client_order_id))) is not None
        ]
        for position in positions:
            symbol = str(position.symbol)
            quantity = float(position.qty)
            held = [(order, tag) for order, tag in tagged if str(order.symbol) == symbol]
            if not held or quantity == 0:
                self._claims[symbol] = None
                continue
            key = held[0][1].strategy
            strategy = self._strategies[key]
            entry_order, entry_tag = next(
                ((order, tag) for order, tag in held if tag.kind == "e" and tag.strategy == key),
                held[0],
            )
            entry = float(position.avg_entry_price)
            risk = entry * entry_tag.risk_fraction
            entered_at = entry_order.filled_at or datetime.now(UTC)
            direction: Direction = 1 if quantity > 0 else -1
            original = abs(float(entry_order.filled_qty or entry_order.qty or position.qty))
            holding = Holding(
                strategy,
                symbol,
                direction,
                entry,
                entry - direction * risk,
                risk,
                entered_at,
                entry,
                entry,
            )
            holding.ladder = strategy.ladder(holding, original, abs(quantity))
            self._holdings[symbol] = holding
            self._claims[symbol] = key
            traded_on = entered_at.astimezone(TRADING_ZONE).date()
            self._traded[strategy.family].add((traded_on, symbol))
            if not self._is_runnable(strategy):
                self._record(
                    f"strategy.exits_only.{key}",
                    "warning",
                    f"{strategy.name()} is managing existing positions only",
                    key,
                )

    def _positions(self) -> dict[str, Any]:
        return {str(value.asset.symbol): value for value in cast(list[Any], self.get_positions())}

    def _reconcile(self, now: datetime) -> None:
        positions = self._positions()
        for symbol in list(self._holdings):
            if symbol not in positions:
                self._release(symbol)
        active = {
            str(order.asset.symbol)
            for order in cast(list[Any], self.get_orders())
            if order.is_active()
        }
        for symbol, pending in list(self._pending.items()):
            ttl = timedelta(minutes=settings.portfolio.pending_ttl_minutes)
            expired = now - pending.submitted_at > ttl
            if symbol not in positions and symbol not in active and expired:
                self._release(symbol)
        for symbol in set(self._stops).difference(active):
            self._stops.pop(symbol, None)
        self._closing.intersection_update(active)
        self._resync_stops(positions)

    def _resync_stops(self, positions: dict[str, Any]) -> None:
        for symbol, holding in self._holdings.items():
            if not holding.strategy.is_stop_resting or symbol in self._closing:
                continue
            position = positions.get(symbol)
            if position is None:
                continue
            quantity = abs(float(position.quantity))
            if quantity <= 0:
                continue
            ladder = holding.ladder
            if ladder is not None and ladder.stage == 0:
                ladder.original_quantity = max(ladder.original_quantity, quantity)
            resting = self._stops.get(symbol)
            if resting is None or resting[1] < quantity - STOP_COVERAGE_DRIFT_MAX:
                self.protect(holding, quantity)

    def _prepare(self, now: datetime) -> None:
        day = now.date()
        if self._prepared_on == day:
            return
        if self._preparation_attempts_on != day:
            self._preparation_attempts_on = day
            self._preparation_attempts = 0
        if self._preparation_attempts >= settings.portfolio.preparation_attempts_max:
            return
        self._preparation_attempts += 1
        first = day - timedelta(days=settings.universe.past_days)
        start = datetime.combine(first, time(), TRADING_ZONE)
        try:
            symbols = self._given or eligible(self.live.listing())
            held = set(self._holdings)
            requested = sorted(set(symbols).union({settings.benchmark_symbol}, held))
            daily_frames = self.past.bars(
                requested,
                cast(TimeFrame, TimeFrame.Day),
                start,
                now,
                settings.past.daily_feed,
            )
            market = self._market(start, now)
            if market is not None:
                daily_frames[MARKET_SYMBOL] = market
        except Exception as error:
            self._daily_frames = {}
            self._eligible_symbols = []
            self._record("universe.unavailable", "error", f"Stock universe unavailable: {error}")
            return
        self._daily_frames = daily_frames
        self._eligible_symbols = list(symbols)
        self._prepared_on = day

    def _market(self, start: datetime, end: datetime) -> DataFrame | None:
        try:
            return self.past.market(start, end)
        except Exception as error:
            self._record(
                "market.unavailable",
                "error",
                f"SPX market state unavailable: {type(error).__name__}",
            )
            return None

    def _completed(self, frame: DataFrame, now: datetime, minutes: int = 0) -> DataFrame:
        index = cast(DatetimeIndex, frame.index)
        if minutes:
            mask = cast(Any, index) + timedelta(minutes=minutes) <= now
            return cast(DataFrame, frame[mask])
        return frame[index.date < now.date()]

    def enter(self, strategy: Strategy, candidate: Candidate, session: Session) -> bool:
        now = session.now
        symbol, price, stop = candidate.symbol, candidate.price, candidate.stop
        direction = candidate.direction
        if (
            not self._is_runnable(strategy)
            or self._is_claimed(symbol)
            or direction * (price - stop) <= 0
        ):
            return False
        if direction == -1 and not self.live.is_shortable(symbol):
            self.record(
                strategy,
                f"short.refused.{symbol}.{now.date()}",
                "warning",
                f"Short entry skipped for {symbol}: security is not shortable",
            )
            return False
        equity = self._equity()
        positions = list(self._positions().values())
        gross = sum(
            abs(float(position.quantity) * float(self.get_last_price(position.asset)))
            for position in positions
        ) + sum(pending.notional for pending in self._pending.values())
        if len(positions) + len(self._pending) >= settings.risk.positions_max or gross >= equity:
            self.record(
                strategy,
                f"portfolio.capped.{symbol}.{now.date()}",
                "warning",
                f"{symbol} entry skipped: portfolio position capacity reached",
            )
            return False
        if equity <= 0:
            return False
        risk_fraction = strategy.risk_fraction_max
        if risk_fraction is None:
            risk_fraction = settings.risk.per_trade_max
        quantity = entry_quantity(
            equity,
            price,
            abs(price - stop),
            settings.risk.position_fraction_max,
            risk_fraction,
            is_fractional_allowed(direction, settings.risk.fractional_orders),
        )
        notional = float(quantity) * price
        if quantity <= 0 or gross + notional > equity:
            self.record(
                strategy,
                f"size.rejected.{symbol}.{now.date()}",
                "warning",
                f"{symbol} entry skipped: no affordable position size",
            )
            return False
        holding = Holding(
            strategy,
            symbol,
            direction,
            price,
            stop,
            abs(price - stop),
            now.astimezone(UTC),
            price,
            price,
        )
        self._pending[symbol] = Pending(holding, now, notional)
        self._claims[symbol] = strategy.key
        order = self.create_order(
            symbol,
            quantity,
            "buy" if direction == 1 else "sell",
            time_in_force="day",
            custom_params={
                "client_order_id": order_tag(strategy.key, "e", symbol, holding.risk / price)
            },
        )
        self.submit_order(order)
        self._traded[strategy.family].add((now.date(), symbol))
        return True

    def protect(self, holding: Holding, quantity: float | None = None) -> None:
        if holding.symbol in self._closing:
            return
        amount = self._quantity(holding.symbol) if quantity is None else quantity
        price = self.last_price(holding.symbol)
        stop = round_stop(holding.direction, holding.stop)
        if amount <= 0 or stop <= 0:
            self.record(
                holding.strategy,
                f"stop.unplaced.{holding.symbol}.{holding.entered_at.date()}",
                "warning",
                f"{holding.symbol} has no resting stop yet: position not readable",
            )
            return
        if (holding.direction == 1 and stop >= price) or (
            holding.direction == -1 and stop <= price
        ):
            self.record(
                holding.strategy,
                f"stop.passed.{holding.symbol}.{holding.entered_at.date()}",
                "warning",
                f"{holding.symbol} is already through its stop at {price:.2f}: closing at market",
            )
            self.exit(holding)
            return
        size = quantity_value(
            amount,
            is_fractional_allowed(holding.direction, settings.risk.fractional_orders),
        )
        if size <= 0 or self._stops.get(holding.symbol) == (stop, float(size)):
            return
        self._cancel(holding.symbol, stops_only=True)
        order = self.create_order(
            holding.symbol,
            size,
            "sell" if holding.direction == 1 else "buy",
            stop_price=stop,
            time_in_force="day",
            custom_params={
                "client_order_id": order_tag(
                    holding.strategy.key, "s", holding.symbol, holding.risk / holding.entry
                )
            },
        )
        self.submit_order(order)
        self._stops[holding.symbol] = (stop, float(size))

    def exit(self, holding: Holding, quantity: float | None = None) -> None:
        if holding.symbol in self._closing:
            return
        current = self._quantity(holding.symbol)
        amount = current if quantity is None else min(quantity, current)
        if amount <= 0:
            self._release(holding.symbol)
            return
        size = quantity_value(
            amount,
            is_fractional_allowed(holding.direction, settings.risk.fractional_orders),
        )
        if size <= 0:
            return
        self._cancel(holding.symbol)
        order = self.create_order(
            holding.symbol,
            size,
            "sell" if holding.direction == 1 else "buy",
            time_in_force="day",
            custom_params={
                "client_order_id": order_tag(
                    holding.strategy.key, "x", holding.symbol, holding.risk / holding.entry
                )
            },
        )
        self.submit_order(order)
        self._closing.add(holding.symbol)

    def _cancel(self, symbol: str, *, stops_only: bool = False) -> None:
        def matches(order: Any) -> bool:
            if not order.is_active() or str(order.asset.symbol) != symbol:
                return False
            return not stops_only or bool(order.is_stop_order())

        orders = [order for order in cast(list[Any], self.get_orders()) if matches(order)]
        self.cancel_open_orders(orders)
        if orders:
            self.sleep(1)
        self._stops.pop(symbol, None)

    def _quantity(self, symbol: str) -> float:
        position = self.get_position(symbol)
        return 0.0 if position is None else abs(float(position.quantity))

    def _is_claimed(self, symbol: str) -> bool:
        return symbol in self._claims or symbol in self._pending or symbol in self._holdings

    def _release(self, symbol: str) -> None:
        self._pending.pop(symbol, None)
        self._holdings.pop(symbol, None)
        self._claims.pop(symbol, None)
        self._stops.pop(symbol, None)
        self._closing.discard(symbol)
