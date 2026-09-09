from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, cast
from uuid import uuid4

from alpaca.trading.models import Asset
from lumibot.strategies import Strategy as LumibotStrategy
from pandas import DataFrame, DatetimeIndex

from mt.config.bot import settings
from mt.config.values import StrategyKey, is_strategy_key
from mt.data.bars import BarsAlpaca
from mt.data.broker import Broker, BrokerAlpaca, BrokerEngine
from mt.data.finnhub import stocks
from mt.exchange import TRADING_ZONE, session_bounds
from mt.frames import last_close, normalize_ohlcv
from mt.indicators import average_turnover_usd, daily_indicators
from mt.position import entry_quantity, round_quantity, round_stop
from mt.snapshot import EventLevel
from mt.strategies.base import Candidate, Position, Session, Strategy, ranked
from mt.strategies.daily import Daily
from mt.strategies.order_tag import order_tag
from mt.strategies.registry import STRATEGIES

from .export import StateExporter


@dataclass(slots=True)
class Pending:
    position: Position
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
            raise ValueError("a backtest needs its symbols")
        self._broker: Broker = BrokerEngine(given) if given else BrokerAlpaca()
        self._bars = BarsAlpaca()
        self._given = given
        self._selected = set(selected)
        self._strategies: dict[StrategyKey, Strategy] = {cls.key: cls(self) for cls in STRATEGIES}
        self._positions: dict[str, Position] = {}
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
        self._assets: dict[str, Asset] = {}
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
        for position in list(self._positions.values()):
            if position.symbol not in self._pending and position.symbol not in self._closing:
                position.strategy.manage(position, session)
        for strategy in self._strategies.values():
            if self._is_runnable(strategy):
                strategy.run(session)

    def before_market_closes(self) -> None:
        for position in list(self._positions.values()):
            if position.strategy.is_stop_resting:
                self.exit(position)

    def on_partially_filled_order(
        self, position: Any, order: Any, price: float, quantity: float | int, multiplier: float
    ) -> None:
        self._fill(position, order, price, quantity, complete=False)

    def on_filled_order(
        self, position: Any, order: Any, price: float, quantity: float | int, multiplier: float
    ) -> None:
        self._fill(position, order, price, quantity, complete=True)

    def _fill(
        self,
        engine_position: Any,
        order: Any,
        price: float,
        quantity: float | int,
        *,
        complete: bool,
    ) -> None:
        symbol = str(order.asset.symbol)
        side = str(order.side).lower()
        pending = self._pending.get(symbol)
        entry_side = "buy" if pending is None or pending.position.direction == 1 else "sell"
        if pending is not None and entry_side in side:
            position = pending.position
            first_fill = pending.filled_quantity == 0
            pending.filled_quantity += abs(float(quantity))
            pending.filled_value += abs(float(quantity)) * price
            position.entry = pending.filled_value / pending.filled_quantity
            if not position.strategy.is_stop_resting:
                position.stop = position.entry - position.direction * position.stop_distance
            else:
                position.stop_distance = abs(position.entry - position.stop)
            position.highest = price if first_fill else max(position.highest, price)
            position.lowest = price if first_fill else min(position.lowest, price)
            position.ladder = position.strategy.ladder(position, pending.filled_quantity)
            self._positions[symbol] = position
            pending.notional = max(0.0, pending.notional - abs(float(quantity)) * price)
            if complete:
                self._pending.pop(symbol)
            if self._locked_at == self.get_datetime().astimezone(TRADING_ZONE).date():
                self._liquidate()
            elif position.strategy.is_stop_resting:
                self.protect(position, abs(float(engine_position.quantity)))
            return
        if complete:
            self._closing.discard(symbol)
        remaining = abs(float(getattr(engine_position, "quantity", 0.0)))
        if remaining <= 0:
            self._release(symbol)
        elif symbol in self._positions and complete:
            self.protect(self._positions[symbol], remaining)

    def symbols(self) -> list[str]:
        return self._symbols

    def daily_frame(self, symbol: str) -> DataFrame | None:
        return self._daily_frames.get(symbol)

    def benchmark_frame(self) -> DataFrame | None:
        return self._daily_frames.get(settings.benchmark_symbol)

    def minute_frames(
        self, symbols: list[str], start: datetime, now: datetime, minutes: int
    ) -> dict[str, DataFrame]:
        frames = self._bars.bars(symbols, f"{minutes}Min", start, now, settings.bars.intraday_feed)
        return {symbol: self._completed(frame, now, minutes) for symbol, frame in frames.items()}

    def last_price(self, symbol: str) -> float:
        return float(self.get_last_price(symbol))

    def position_count(self, keys: frozenset[StrategyKey]) -> int:
        held = sum(1 for position in self._positions.values() if position.strategy.key in keys)
        ordered = sum(
            1
            for symbol, pending in self._pending.items()
            if pending.position.strategy.key in keys and symbol not in self._positions
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
        strategy_key: StrategyKey | None = None,
    ) -> None:
        if kind in self._events:
            return
        self._events.add(kind)
        if self.exporter is not None:
            self.exporter.publish("running", kind, level, message, strategy_key=strategy_key)

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
            f"Intraday bars come from the broker's {settings.bars.intraday_feed} feed",
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
            self._closing = self._broker.cancel_orders()
        self._liquidate()

    def _liquidate(self) -> None:
        if self.is_backtesting:
            quantities = {
                symbol: float(position.quantity)
                for symbol, position in self._engine_positions().items()
                if str(position.asset.asset_type) == "stock"
            }
        else:
            quantities = {
                position.symbol: float(position.qty) for position in self._broker.positions()
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

    def _engine_positions(self) -> dict[str, Any]:
        return {str(value.asset.symbol): value for value in cast(list[Any], self.get_positions())}

    def _reconcile(self, now: datetime) -> None:
        positions = self._engine_positions()
        for symbol in list(self._positions):
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
        for symbol, position in self._positions.items():
            if not position.strategy.is_stop_resting or symbol in self._closing:
                continue
            engine_position = positions.get(symbol)
            if engine_position is None:
                continue
            quantity = abs(float(engine_position.quantity))
            if quantity <= 0:
                continue
            ladder = position.ladder
            if ladder is not None and ladder.stage == 0:
                ladder.original_quantity = max(ladder.original_quantity, quantity)
            resting = self._stops.get(symbol)
            drift_max = settings.portfolio.stop_coverage_drift_max
            if resting is None or resting[1] < quantity - drift_max:
                self.protect(position, quantity)

    def _prepare(self, now: datetime) -> None:
        day = now.date()
        if self._prepared_at == day:
            return
        first = day - timedelta(days=settings.portfolio.lookback_days)
        start = datetime.combine(first, time(), TRADING_ZONE)
        self._assets = self._broker.assets()
        symbols = self._given or self._screen(now, self._assets)
        requested = sorted(set(symbols).union({settings.benchmark_symbol}, self._positions))
        frames: dict[str, DataFrame] = {}
        if self.is_backtesting and all(
            isinstance(self._strategies[key], Daily) for key in self._selected
        ):
            for symbol in requested:
                bars = self.get_historical_prices(
                    symbol, settings.portfolio.lookback_days, timestep="day"
                )
                if bars is not None:
                    frames[symbol] = normalize_ohlcv(bars.df, {"high", "low", "close", "volume"})
        else:
            frames = self._bars.bars(requested, "1Day", start, now, settings.bars.daily_feed)
        lengths = {
            length
            for strategy in self._strategies.values()
            if isinstance(strategy, Daily)
            for length in strategy.sma_lengths()
        }
        period = settings.indicators.period
        self._daily_frames = {
            symbol: daily_indicators(self._completed(frame, now), lengths, period)
            for symbol, frame in frames.items()
        }
        self._symbols = list(symbols)
        self._prepared_at = day

    def _screen(self, now: datetime, assets: dict[str, Asset]) -> list[str]:
        symbols = sorted(assets.keys() & stocks())
        first = now.date() - timedelta(days=settings.screen.lookback_days)
        start = datetime.combine(first, time(), TRADING_ZONE)
        frames = self._bars.bars(symbols, "1Day", start, now, settings.bars.daily_feed)
        cleared: dict[str, float] = {}
        for symbol, frame in frames.items():
            completed = self._completed(frame, now)
            if completed.empty or last_close(completed) < settings.screen.price_usd_min:
                continue
            turnover = average_turnover_usd(completed, settings.screen.turnover_sessions)
            if turnover >= settings.screen.turnover_usd_min:
                cleared[symbol] = turnover
        return ranked(
            cleared, symbol=lambda symbol: symbol, turnover=lambda symbol: cleared[symbol]
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
        positions = self._engine_positions()
        owned = positions.keys() | self._pending.keys()
        if (
            not self._is_runnable(strategy)
            or symbol in owned
            or symbol in self._positions
            or direction * (price - stop) <= 0
        ):
            return False
        if direction == -1 and (symbol not in self._assets or not self._assets[symbol].shortable):
            self.record(
                strategy,
                f"short.refused.{symbol}.{now.date()}",
                "warning",
                f"Short entry skipped for {symbol}: security is not shortable",
            )
            return False
        equity = self._equity()
        gross = sum(
            abs(float(position.quantity) * float(self.get_last_price(position.asset)))
            for position in positions.values()
        ) + sum(pending.notional for pending in self._pending.values())
        if len(owned) >= settings.risk.positions_max or gross >= equity:
            self.record(
                strategy,
                f"portfolio.capped.{symbol}.{now.date()}",
                "warning",
                f"{symbol} entry skipped: portfolio position capacity reached",
            )
            return False
        equity_risk_fraction = strategy.equity_risk_fraction_max
        if equity_risk_fraction is None:
            equity_risk_fraction = settings.risk.per_trade_max
        quantity = entry_quantity(
            equity,
            price,
            abs(price - stop),
            settings.risk.position_fraction_max,
            equity_risk_fraction,
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
        position = Position(
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
        self._pending[symbol] = Pending(position, now, notional)
        order = self.create_order(
            symbol,
            quantity,
            "buy" if direction == 1 else "sell",
            time_in_force="day",
            custom_params={
                "client_order_id": order_tag(
                    strategy.key, "e", symbol, position.stop_distance / price
                )
            },
        )
        self._traded[strategy.key].add((now.date(), symbol))
        self.submit_order(order)
        return True

    def protect(self, position: Position, quantity: float | None = None) -> None:
        if (
            position.symbol in self._closing
            or not position.strategy.is_stop_resting
            or self._locked_at == self.get_datetime().astimezone(TRADING_ZONE).date()
        ):
            return
        amount = self._quantity(position.symbol) if quantity is None else quantity
        price = self.last_price(position.symbol)
        stop = round_stop(position.direction, position.stop)
        if amount <= 0 or stop <= 0:
            self.record(
                position.strategy,
                f"stop.unplaced.{position.symbol}.{position.entered_at.date()}",
                "warning",
                f"{position.symbol} has no resting stop yet: "
                "quantity or stop price is not positive",
            )
            return
        if (position.direction == 1 and stop >= price) or (
            position.direction == -1 and stop <= price
        ):
            self.record(
                position.strategy,
                f"stop.passed.{position.symbol}.{position.entered_at.date()}",
                "warning",
                f"{position.symbol} is already through its stop at {price:.2f}: closing at market",
            )
            self.exit(position)
            return
        size = round_quantity(amount)
        if size <= 0 or self._stops.get(position.symbol) == (stop, float(size)):
            return
        self._cancel(position.symbol, stops_only=True)
        order = self.create_order(
            position.symbol,
            size,
            "sell" if position.direction == 1 else "buy",
            stop_price=stop,
            time_in_force="day",
            custom_params={
                "client_order_id": order_tag(
                    position.strategy.key,
                    "s",
                    position.symbol,
                    position.stop_distance / position.entry,
                )
            },
        )
        self.submit_order(order)
        self._stops[position.symbol] = (stop, float(size))

    def exit(self, position: Position, quantity: float | None = None) -> None:
        if position.symbol in self._closing:
            return
        current = self._quantity(position.symbol)
        amount = current if quantity is None else min(quantity, current)
        if amount <= 0:
            self._release(position.symbol)
            return
        size = round_quantity(amount, whole=position.direction == -1 and quantity is not None)
        if size <= 0:
            return
        self._cancel(position.symbol)
        order = self.create_order(
            position.symbol,
            size,
            "sell" if position.direction == 1 else "buy",
            time_in_force="day",
            custom_params={
                "client_order_id": order_tag(
                    position.strategy.key,
                    "x",
                    position.symbol,
                    position.stop_distance / position.entry,
                )
            },
        )
        self._closing.add(position.symbol)
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
        return symbol in self._pending or symbol in self._positions or self._quantity(symbol) > 0

    def _release(self, symbol: str) -> None:
        self._pending.pop(symbol, None)
        self._positions.pop(symbol, None)
        self._stops.pop(symbol, None)
        self._closing.discard(symbol)
