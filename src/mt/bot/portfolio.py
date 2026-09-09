from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, cast
from uuid import uuid4

from lumibot.strategies import Strategy as LumibotStrategy
from pandas import DataFrame, DatetimeIndex

from mt.config.bot import settings
from mt.config.values import StrategyKey, is_strategy_key
from mt.data.finnhub import stocks
from mt.data.live import BrokerLive, EngineLive, Live
from mt.data.past import Past
from mt.exchange import TRADING_ZONE, session_bounds
from mt.frames import last_close, normalize_ohlcv
from mt.indicators import average_turnover_usd
from mt.position import entry_quantity, round_quantity, round_stop
from mt.snapshot import EventLevel
from mt.strategies.base import Candidate, Holding, Session, Strategy, ranked
from mt.strategies.daily import Daily
from mt.strategies.order_tag import order_tag
from mt.strategies.registry import STRATEGIES

from .export import StateExporter


@dataclass(slots=True)
class Pending:
    holding: Holding
    submitted_at: datetime
    notional: float
    filled_quantity: float = 0.0
    filled_value: float = 0.0


class Portfolio(LumibotStrategy):
    exporter: StateExporter | None = None

    def on_bot_crash(self, error: Exception) -> None:
        if self.exporter is not None:
            self.exporter.publish("failed", "run.crashed", "error", type(error).__name__)

    def on_abrupt_closing(self) -> None:
        if self.exporter is not None:
            self.exporter.close("stopped", "Trading run stopped")

    def on_strategy_end(self) -> None:
        self.on_abrupt_closing()

    def initialize(self) -> None:
        self.sleeptime = f"{settings.portfolio.iteration_minutes}M"
        self.minutes_before_opening = settings.portfolio.opening_lead_minutes
        supplied = cast(list[str], self.parameters["strategies"])
        selected: list[StrategyKey] = [value for value in supplied if is_strategy_key(value)]
        if len(selected) != len(supplied):
            raise ValueError("strategies parameter contains unknown strategy keys")
        given = cast(list[str] | None, self.parameters.get("symbols"))
        if self.is_backtesting and not given:
            raise ValueError("a replay needs its symbols")
        self.live: Live = EngineLive(given) if given else BrokerLive()
        self.past = Past()
        self._given = given
        self._selected = set(selected)
        self._strategies: dict[StrategyKey, Strategy] = {cls.key: cls(self) for cls in STRATEGIES}
        self._holdings: dict[str, Holding] = {}
        self._pending: dict[str, Pending] = {}
        self._stops: dict[str, tuple[float, float]] = {}
        self._closing: set[str] = set()
        self._events: set[str] = set()
        self._traded: dict[StrategyKey, set[tuple[date, str]]] = {
            cls.key: set() for cls in STRATEGIES
        }
        self._day: date | None = None
        self._session_baseline = 0.0
        self._locked_at: date | None = None
        self._daily_frames: dict[str, DataFrame] = {}
        self._symbols: list[str] = []
        self._shorts: frozenset[str] = frozenset()
        self._prepared_at: date | None = None

    def before_market_opens(self) -> None:
        self._prepare(self.get_datetime().astimezone(TRADING_ZONE))

    def on_trading_iteration(self) -> None:
        now = self.get_datetime().astimezone(TRADING_ZONE)
        bounds = session_bounds(now.date())
        if bounds is None:
            return
        opens, closes = bounds
        session = Session(now, opens, closes)
        self._begin_day(now.date())
        self._reconcile(now)
        self._emergency_exit(now.date())
        if self._locked_at == now.date():
            return
        self._prepare(now)
        for holding in list(self._holdings.values()):
            if holding.symbol not in self._pending and holding.symbol not in self._closing:
                holding.strategy.manage(holding, session)
        for strategy in self._strategies.values():
            if self._is_runnable(strategy):
                strategy.run(session)

    def before_market_closes(self) -> None:
        for holding in list(self._holdings.values()):
            if holding.strategy.is_stop_resting:
                self.exit(holding)

    def on_partially_filled_order(
        self, position: Any, order: Any, price: float, quantity: float | int, multiplier: float
    ) -> None:
        self._fill(position, order, price, quantity, complete=False)

    def on_filled_order(
        self, position: Any, order: Any, price: float, quantity: float | int, multiplier: float
    ) -> None:
        self._fill(position, order, price, quantity, complete=True)

    def _fill(
        self, position: Any, order: Any, price: float, quantity: float | int, *, complete: bool
    ) -> None:
        symbol = str(order.asset.symbol)
        side = str(order.side).lower()
        pending = self._pending.get(symbol)
        entry_side = "buy" if pending is None or pending.holding.direction == 1 else "sell"
        if pending is not None and entry_side in side:
            holding = pending.holding
            first_fill = pending.filled_quantity == 0
            pending.filled_quantity += abs(float(quantity))
            pending.filled_value += abs(float(quantity)) * price
            holding.entry = pending.filled_value / pending.filled_quantity
            if not holding.strategy.is_stop_resting:
                holding.stop = holding.entry - holding.direction * holding.risk
            else:
                holding.risk = abs(holding.entry - holding.stop)
            holding.highest = price if first_fill else max(holding.highest, price)
            holding.lowest = price if first_fill else min(holding.lowest, price)
            holding.ladder = holding.strategy.ladder(holding, pending.filled_quantity)
            self._holdings[symbol] = holding
            pending.notional = max(0.0, pending.notional - abs(float(quantity)) * price)
            if complete:
                self._pending.pop(symbol)
            if self._locked_at == self.get_datetime().astimezone(TRADING_ZONE).date():
                self._liquidate()
            elif holding.strategy.is_stop_resting:
                self.protect(holding, abs(float(position.quantity)))
            return
        if complete:
            self._closing.discard(symbol)
        remaining = abs(float(getattr(position, "quantity", 0.0)))
        if remaining <= 0:
            self._release(symbol)
        elif symbol in self._holdings and complete:
            self.protect(self._holdings[symbol], remaining)

    def symbols(self) -> list[str]:
        return self._symbols

    def daily_frame(self, symbol: str, now: datetime) -> DataFrame | None:
        frame = self._daily_frames.get(symbol)
        return None if frame is None else self._completed(frame, now)

    def benchmark_frame(self, now: datetime) -> DataFrame | None:
        return self.daily_frame(settings.benchmark_symbol, now)

    def minute_frames(
        self, symbols: list[str], start: datetime, now: datetime, minutes: int
    ) -> dict[str, DataFrame]:
        frames = self.past.bars(symbols, f"{minutes}Min", start, now, settings.past.intraday_feed)
        return {symbol: self._completed(frame, now, minutes) for symbol, frame in frames.items()}

    def last_price(self, symbol: str) -> float:
        return float(self.get_last_price(symbol))

    def position_count(self, keys: frozenset[StrategyKey]) -> int:
        held = sum(1 for holding in self._holdings.values() if holding.strategy.key in keys)
        ordered = sum(
            1
            for symbol, pending in self._pending.items()
            if pending.holding.strategy.key in keys and symbol not in self._holdings
        )
        return held + ordered

    def is_taken(self, strategy: Strategy, symbol: str, day: date) -> bool:
        return self._is_owned(symbol) or (day, symbol) in self._traded[strategy.key]

    def record(self, strategy: Strategy, kind: str, level: EventLevel, message: str) -> None:
        self._record(f"{strategy.key}.{kind}", level, message, strategy.key)

    def _is_runnable(self, strategy: Strategy) -> bool:
        return strategy.key in self._selected and not strategy.is_paused

    def _record(
        self,
        kind: str,
        level: EventLevel,
        message: str,
        strategy: StrategyKey | None = None,
    ) -> None:
        if kind in self._events:
            return
        self._events.add(kind)
        if self.exporter is not None:
            self.exporter.publish("running", kind, level, message, strategy=strategy)

    def _equity(self) -> float:
        value = self.get_portfolio_value()
        if value is None:
            raise RuntimeError("portfolio value is unavailable")
        return float(value)

    def _begin_day(self, day: date) -> None:
        if day == self._day:
            return
        self._day = day
        self._session_baseline = self._equity()
        self._events.clear()
        for strategy in self._strategies.values():
            if strategy.key in self._selected and strategy.is_paused:
                self._record(
                    f"strategy.paused.{strategy.key}",
                    "warning",
                    f"{strategy.name()} is paused: no new entries",
                    strategy.key,
                )
        self._record(
            "feed.announced",
            "info",
            f"Intraday candles come from the broker's {settings.past.intraday_feed} feed",
        )
        for strategy in self._strategies.values():
            strategy.begin(day)

    def _emergency_exit(self, day: date) -> None:
        if self._locked_at != day:
            if self._equity() > self._session_baseline * (1.0 - settings.risk.per_day_max):
                return
            self._locked_at = day
            if self.is_backtesting:
                self.cancel_open_orders()
                self._closing.clear()
            self._stops.clear()
            self._record("day.locked", "warning", "Daily loss limit reached")
        if not self.is_backtesting:
            self._closing = self.live.cancel_orders()
        self._liquidate()

    def _liquidate(self) -> None:
        if self.is_backtesting:
            quantities = {
                symbol: float(position.quantity)
                for symbol, position in self._positions().items()
                if str(position.asset.asset_type) == "stock"
            }
        else:
            quantities = {
                position.symbol: float(position.qty) for position in self.live.positions()
            }
        for symbol, quantity in quantities.items():
            if not quantity or symbol in self._closing:
                continue
            order = self.create_order(
                symbol,
                abs(quantity),
                "sell" if quantity > 0 else "buy",
                time_in_force="day",
                custom_params={"client_order_id": f"mt-liquidate-{uuid4().hex}"},
            )
            self._closing.add(symbol)
            self.submit_order(order)

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
            if symbol not in active and expired:
                self._pending.pop(symbol, None)
                if symbol not in positions:
                    self._release(symbol)
        for symbol in set(self._stops).difference(active):
            self._stops.pop(symbol, None)
        self._closing.intersection_update(active)
        if self._locked_at != now.date():
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
            drift_max = settings.portfolio.stop_coverage_drift_max
            if resting is None or resting[1] < quantity - drift_max:
                self.protect(holding, quantity)

    def _prepare(self, now: datetime) -> None:
        day = now.date()
        if self._prepared_at == day:
            return
        first = day - timedelta(days=settings.portfolio.past_days)
        start = datetime.combine(first, time(), TRADING_ZONE)
        listing = self.live.listing()
        symbols = self._given or self._screen(now, listing.symbols)
        held = set(self._holdings)
        requested = sorted(set(symbols).union({settings.benchmark_symbol}, held))
        if self.is_backtesting and all(
            isinstance(self._strategies[key], Daily) for key in self._selected
        ):
            self._daily_frames = {}
            for symbol in requested:
                bars = self.get_historical_prices(
                    symbol, settings.portfolio.past_days, timestep="day"
                )
                if bars is not None:
                    self._daily_frames[symbol] = normalize_ohlcv(
                        bars.df, {"high", "low", "close", "volume"}
                    )
        else:
            self._daily_frames = self.past.bars(
                requested, "1Day", start, now, settings.past.daily_feed
            )
        self._symbols = list(symbols)
        self._shorts = listing.shorts
        self._prepared_at = day

    def _screen(self, now: datetime, listing: frozenset[str]) -> list[str]:
        symbols = sorted(listing & stocks())
        first = now.date() - timedelta(days=settings.screen.past_days)
        start = datetime.combine(first, time(), TRADING_ZONE)
        frames = self.past.bars(symbols, "1Day", start, now, settings.past.daily_feed)
        return ranked(
            (symbol for symbol, frame in frames.items() if self._does_clear(frame, now)),
            symbol=lambda symbol: symbol,
            turnover=lambda symbol: average_turnover_usd(
                self._completed(frames[symbol], now), settings.screen.turnover_sessions
            ),
        )

    def _does_clear(self, frame: DataFrame, now: datetime) -> bool:
        completed = self._completed(frame, now)
        if completed.empty:
            return False
        return (
            last_close(completed) >= settings.screen.price_usd_min
            and average_turnover_usd(completed, settings.screen.turnover_sessions)
            >= settings.screen.turnover_usd_min
        )

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
            or self._is_owned(symbol)
            or direction * (price - stop) <= 0
        ):
            return False
        if direction == -1 and symbol not in self._shorts:
            self.record(
                strategy,
                f"short.refused.{symbol}.{now.date()}",
                "warning",
                f"Short entry skipped for {symbol}: security is not shortable",
            )
            return False
        equity = self._equity()
        positions = self._positions()
        gross = sum(
            abs(float(position.quantity) * float(self.get_last_price(position.asset)))
            for position in positions.values()
        ) + sum(pending.notional for pending in self._pending.values())
        if (
            len(positions.keys() | self._pending.keys()) >= settings.risk.positions_max
            or gross >= equity
        ):
            self.record(
                strategy,
                f"portfolio.capped.{symbol}.{now.date()}",
                "warning",
                f"{symbol} entry skipped: portfolio position capacity reached",
            )
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
            settings.risk.notional_usd_min,
            direction,
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
        order = self.create_order(
            symbol,
            quantity,
            "buy" if direction == 1 else "sell",
            time_in_force="day",
            custom_params={
                "client_order_id": order_tag(strategy.key, "e", symbol, holding.risk / price)
            },
        )
        self._traded[strategy.key].add((now.date(), symbol))
        self.submit_order(order)
        return True

    def protect(self, holding: Holding, quantity: float | None = None) -> None:
        if (
            holding.symbol in self._closing
            or not holding.strategy.is_stop_resting
            or self._locked_at == self.get_datetime().astimezone(TRADING_ZONE).date()
        ):
            return
        amount = self._quantity(holding.symbol) if quantity is None else quantity
        price = self.last_price(holding.symbol)
        stop = round_stop(holding.direction, holding.stop)
        if amount <= 0 or stop <= 0:
            self.record(
                holding.strategy,
                f"stop.unplaced.{holding.symbol}.{holding.entered_at.date()}",
                "warning",
                f"{holding.symbol} has no resting stop yet: quantity or stop price is not positive",
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
        size = round_quantity(amount)
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
        size = round_quantity(amount, whole=holding.direction == -1 and quantity is not None)
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
        self._closing.add(holding.symbol)
        self.submit_order(order)

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

    def _is_owned(self, symbol: str) -> bool:
        return symbol in self._pending or symbol in self._holdings or self._quantity(symbol) > 0

    def _release(self, symbol: str) -> None:
        self._pending.pop(symbol, None)
        self._holdings.pop(symbol, None)
        self._stops.pop(symbol, None)
        self._closing.discard(symbol)
