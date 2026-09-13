from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, cast
from uuid import uuid4

from lumibot.strategies import Strategy as LumibotStrategy
from pandas import DataFrame, DatetimeIndex

from mt.config.bot import settings as bot_settings
from mt.config.shared import settings
from mt.config.values import StrategyKey, is_strategy_key
from mt.data.asset import Asset, AssetType
from mt.data.broker import Broker, BrokerAlpaca, BrokerAsset, BrokerEngine
from mt.data.earnings import is_earnings_blocked, is_earnings_exit_due
from mt.data.finnhub import stocks
from mt.exchange import TRADING_ZONE, session_bounds
from mt.frames import last_close, normalize_ohlcv
from mt.indicators import average_turnover_usd, daily_indicators
from mt.position import entry_quantity, round_quantity, round_stop
from mt.state import EventLevel
from mt.strategies.base import Candidate, Position, Session, Strategy, ranked
from mt.strategies.daily import Daily
from mt.strategies.order_tag import order_tag
from mt.strategies.registry import STRATEGIES

from .bars import Bars
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
            self.exporter.publish("stopped", "run.stopped", "info", "Trading run stopped")

    def on_strategy_end(self) -> None:
        self.on_abrupt_closing()

    def initialize(self) -> None:
        self.sleeptime = f"{bot_settings.portfolio.iteration_minutes}M"
        self.minutes_before_opening = bot_settings.portfolio.opening_lead_minutes
        supplied = cast(list[str], self.parameters["strategies"])
        selected: list[StrategyKey] = [value for value in supplied if is_strategy_key(value)]
        if len(selected) != len(supplied):
            raise ValueError("strategies parameter contains unknown strategy keys")
        given = cast(list[Asset] | None, self.parameters.get("assets"))
        if self.is_backtesting and not given:
            raise ValueError("a backtest needs its assets")
        if given and any(asset.asset_type != AssetType.STOCK for asset in given):
            raise ValueError("trading strategies support equities only")
        self._broker: Broker = BrokerEngine(given) if given else BrokerAlpaca()
        self._bars = cast(Bars, self.parameters.pop("bars"))
        self._given = given
        self._benchmark = Asset.from_symbol(settings.benchmark_symbol)
        self._selected = set(selected)
        self._strategies: dict[StrategyKey, Strategy] = {cls.key: cls(self) for cls in STRATEGIES}
        self._positions: dict[Asset, Position] = {}
        self._pending: dict[Asset, Pending] = {}
        self._stops: dict[Asset, tuple[float, float]] = {}
        self._closing: set[Asset] = set()
        self._events: set[str] = set()
        self._traded: dict[StrategyKey, set[tuple[date, Asset]]] = {
            cls.key: set() for cls in STRATEGIES
        }
        self._day: date | None = None
        self._session_baseline = 0.0
        self._locked_at: date | None = None
        self._daily_frames: dict[Asset, DataFrame] = {}
        self._assets: list[Asset] = []
        self._permissions: dict[Asset, BrokerAsset] = {}
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
            if position.asset not in self._pending and position.asset not in self._closing:
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
        asset = Asset.from_lumibot(order.asset)
        side = str(order.side).lower()
        pending = self._pending.get(asset)
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
            self._positions[asset] = position
            pending.notional = max(0.0, pending.notional - abs(float(quantity)) * price)
            if complete:
                self._pending.pop(asset)
            if self._locked_at == self.get_datetime().astimezone(TRADING_ZONE).date():
                self._liquidate()
            elif position.strategy.is_stop_resting:
                self.protect(position, abs(float(engine_position.quantity)))
            return
        if complete:
            self._closing.discard(asset)
        remaining = abs(float(getattr(engine_position, "quantity", 0.0)))
        if remaining <= 0:
            self._release(asset)
        elif asset in self._positions and complete:
            self.protect(self._positions[asset], remaining)

    def assets(self) -> list[Asset]:
        return self._assets

    def daily_frame(self, asset: Asset) -> DataFrame | None:
        return self._daily_frames.get(asset)

    def benchmark_frame(self) -> DataFrame | None:
        return self._daily_frames.get(self._benchmark)

    def minute_frames(
        self, assets: list[Asset], start: datetime, now: datetime, minutes: int
    ) -> dict[Asset, DataFrame]:
        frames = self._bars.bars(assets, f"{minutes}Min", start, now)
        return {asset: self._completed(frame, now, minutes) for asset, frame in frames.items()}

    def last_price(self, asset: Asset) -> float:
        return float(self.get_last_price(asset.to_lumibot()))

    def is_earnings_blocked(self, asset: Asset, day: date) -> bool:
        return is_earnings_blocked(asset, day)

    def is_earnings_exit_due(self, asset: Asset, day: date) -> bool:
        return is_earnings_exit_due(asset, day)

    def position_count(self, keys: frozenset[StrategyKey]) -> int:
        held = sum(1 for position in self._positions.values() if position.strategy.key in keys)
        ordered = sum(
            1
            for asset, pending in self._pending.items()
            if pending.position.strategy.key in keys and asset not in self._positions
        )
        return held + ordered

    def is_taken(self, strategy: Strategy, asset: Asset, day: date) -> bool:
        return self._is_owned(asset) or (day, asset) in self._traded[strategy.key]

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
                asset: float(position.quantity)
                for asset, position in self._engine_positions().items()
                if position.asset.asset_type == AssetType.STOCK
            }
        else:
            quantities = {
                Asset.from_symbol(position.symbol): float(position.qty)
                for position in self._broker.positions()
            }
        for asset, quantity in quantities.items():
            if not quantity or asset in self._closing:
                continue
            order = self.create_order(
                asset.to_lumibot(),
                abs(quantity),
                "sell" if quantity > 0 else "buy",
                time_in_force="day",
                custom_params={"client_order_id": f"mt-liquidate-{uuid4().hex}"},
            )
            self._closing.add(asset)
            self.submit_order(order)

    def _engine_positions(self) -> dict[Asset, Any]:
        return {
            Asset.from_lumibot(value.asset): value
            for value in cast(list[Any], self.get_positions())
        }

    def _reconcile(self, now: datetime) -> None:
        positions = self._engine_positions()
        for asset in list(self._positions):
            if asset not in positions:
                self._release(asset)
        active = {
            Asset.from_lumibot(order.asset)
            for order in cast(list[Any], self.get_orders())
            if order.is_active()
        }
        for asset, pending in list(self._pending.items()):
            ttl = timedelta(minutes=bot_settings.portfolio.pending_ttl_minutes)
            expired = now - pending.submitted_at > ttl
            if asset not in active and expired:
                self._pending.pop(asset, None)
                if asset not in positions:
                    self._release(asset)
        for asset in set(self._stops).difference(active):
            self._stops.pop(asset, None)
        self._closing.intersection_update(active)
        if self._locked_at != now.date():
            self._resync_stops(positions)

    def _resync_stops(self, positions: dict[Asset, Any]) -> None:
        for asset, position in self._positions.items():
            if not position.strategy.is_stop_resting or asset in self._closing:
                continue
            engine_position = positions.get(asset)
            if engine_position is None:
                continue
            quantity = abs(float(engine_position.quantity))
            if quantity <= 0:
                continue
            ladder = position.ladder
            if ladder is not None and ladder.stage == 0:
                ladder.original_quantity = max(ladder.original_quantity, quantity)
            resting = self._stops.get(asset)
            drift_max = bot_settings.portfolio.stop_coverage_drift_max
            if resting is None or resting[1] < quantity - drift_max:
                self.protect(position, quantity)

    def _prepare(self, now: datetime) -> None:
        day = now.date()
        if self._prepared_at == day:
            return
        first = day - timedelta(days=bot_settings.portfolio.lookback_days)
        start = datetime.combine(first, time(), TRADING_ZONE)
        self._permissions = self._broker.assets()
        assets = self._given or self._screen(now)
        requested = sorted(
            set(assets).union({self._benchmark}, self._positions),
            key=str,
        )
        frames: dict[Asset, DataFrame] = {}
        if self.is_backtesting and all(
            isinstance(self._strategies[key], Daily) for key in self._selected
        ):
            for asset in requested:
                bars = self.get_historical_prices(
                    asset.to_lumibot(), bot_settings.portfolio.lookback_days, timestep="day"
                )
                if bars is not None:
                    frames[asset] = normalize_ohlcv(bars.df, {"high", "low", "close", "volume"})
        else:
            frames = self._bars.bars(requested, "1Day", start, now)
        lengths = {
            length
            for strategy in self._strategies.values()
            if isinstance(strategy, Daily)
            for length in strategy.sma_lengths()
        }
        period = settings.indicators.period
        self._daily_frames = {
            asset: daily_indicators(self._completed(frame, now), lengths, period)
            for asset, frame in frames.items()
        }
        self._assets = list(assets)
        self._prepared_at = day

    def _screen(self, now: datetime) -> list[Asset]:
        common_stocks = stocks()
        assets = sorted(
            (
                asset
                for asset in self._permissions
                if asset.asset_type == AssetType.STOCK and asset.symbol in common_stocks
            ),
            key=str,
        )
        first = now.date() - timedelta(days=settings.screen.lookback_days)
        start = datetime.combine(first, time(), TRADING_ZONE)
        frames = self._bars.bars(assets, "1Day", start, now)
        cleared: dict[Asset, float] = {}
        for asset, frame in frames.items():
            completed = self._completed(frame, now)
            if completed.empty or last_close(completed) <= settings.screen.price_usd_min:
                continue
            turnover = average_turnover_usd(completed, settings.screen.turnover_sessions)
            if turnover > settings.screen.turnover_usd_min:
                cleared[asset] = turnover
        return ranked(cleared, symbol=str, turnover=lambda asset: cleared[asset])

    def _completed(self, frame: DataFrame, now: datetime, minutes: int = 0) -> DataFrame:
        index = cast(DatetimeIndex, frame.index)
        if minutes:
            mask = cast(Any, index) + timedelta(minutes=minutes) <= now
            return cast(DataFrame, frame[mask])
        return frame[index.date < now.date()]

    def enter(self, strategy: Strategy, candidate: Candidate, session: Session) -> bool:
        now = session.now
        asset, price, stop = candidate.asset, candidate.price, candidate.stop
        direction = candidate.direction
        positions = self._engine_positions()
        owned = positions.keys() | self._pending.keys()
        if (
            asset.asset_type != AssetType.STOCK
            or not self._is_runnable(strategy)
            or asset in owned
            or asset in self._positions
            or direction * (price - stop) <= 0
        ):
            return False
        if direction == -1 and (
            asset not in self._permissions or not self._permissions[asset].shortable
        ):
            self.record(
                strategy,
                f"short.refused.{asset}.{now.date()}",
                "warning",
                f"Short entry skipped for {asset}: security is not shortable",
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
                f"portfolio.capped.{asset}.{now.date()}",
                "warning",
                f"{asset} entry skipped: portfolio position capacity reached",
            )
            return False
        quantity = entry_quantity(equity, price, abs(price - stop), direction)
        notional = float(quantity) * price
        if quantity <= 0 or gross + notional > equity:
            self.record(
                strategy,
                f"size.rejected.{asset}.{now.date()}",
                "warning",
                f"{asset} entry skipped: no affordable position size",
            )
            return False
        position = Position(
            strategy,
            asset,
            direction,
            price,
            stop,
            abs(price - stop),
            now.astimezone(UTC),
            price,
            price,
        )
        self._pending[asset] = Pending(position, now, notional)
        order = self.create_order(
            asset.to_lumibot(),
            quantity,
            "buy" if direction == 1 else "sell",
            time_in_force="day",
            custom_params={
                "client_order_id": order_tag(strategy.key, position.stop_distance / price)
            },
        )
        self._traded[strategy.key].add((now.date(), asset))
        self.submit_order(order)
        return True

    def protect(self, position: Position, quantity: float | None = None) -> None:
        if (
            position.asset in self._closing
            or not position.strategy.is_stop_resting
            or self._locked_at == self.get_datetime().astimezone(TRADING_ZONE).date()
        ):
            return
        amount = self._quantity(position.asset) if quantity is None else quantity
        price = self.last_price(position.asset)
        stop = round_stop(position.direction, position.stop)
        if amount <= 0 or stop <= 0:
            self.record(
                position.strategy,
                f"stop.unplaced.{position.asset}.{position.entered_at.date()}",
                "warning",
                f"{position.asset} has no resting stop yet: quantity or stop price is not positive",
            )
            return
        if (position.direction == 1 and stop >= price) or (
            position.direction == -1 and stop <= price
        ):
            self.record(
                position.strategy,
                f"stop.passed.{position.asset}.{position.entered_at.date()}",
                "warning",
                f"{position.asset} is already through its stop at {price:.2f}: closing at market",
            )
            self.exit(position)
            return
        size = round_quantity(amount)
        if size <= 0 or self._stops.get(position.asset) == (stop, float(size)):
            return
        self._cancel(position.asset, stops_only=True)
        order = self.create_order(
            position.asset.to_lumibot(),
            size,
            "sell" if position.direction == 1 else "buy",
            stop_price=stop,
            time_in_force="day",
            custom_params={
                "client_order_id": order_tag(
                    position.strategy.key,
                    position.stop_distance / position.entry,
                )
            },
        )
        self.submit_order(order)
        self._stops[position.asset] = (stop, float(size))

    def exit(self, position: Position, quantity: float | None = None) -> None:
        if position.asset in self._closing:
            return
        current = self._quantity(position.asset)
        amount = current if quantity is None else min(quantity, current)
        if amount <= 0:
            self._release(position.asset)
            return
        size = round_quantity(amount, whole=position.direction == -1 and quantity is not None)
        if size <= 0:
            return
        self._cancel(position.asset)
        order = self.create_order(
            position.asset.to_lumibot(),
            size,
            "sell" if position.direction == 1 else "buy",
            time_in_force="day",
            custom_params={
                "client_order_id": order_tag(
                    position.strategy.key,
                    position.stop_distance / position.entry,
                )
            },
        )
        self._closing.add(position.asset)
        self.submit_order(order)

    def _cancel(self, asset: Asset, *, stops_only: bool = False) -> None:
        def matches(order: Any) -> bool:
            if not order.is_active() or Asset.from_lumibot(order.asset) != asset:
                return False
            return not stops_only or bool(order.is_stop_order())

        orders = [order for order in cast(list[Any], self.get_orders()) if matches(order)]
        self.cancel_open_orders(orders)
        if orders:
            self.sleep(1)
        self._stops.pop(asset, None)

    def _quantity(self, asset: Asset) -> float:
        position = self.get_position(asset.to_lumibot())
        return 0.0 if position is None else abs(float(position.quantity))

    def _is_owned(self, asset: Asset) -> bool:
        return asset in self._pending or asset in self._positions or self._quantity(asset) > 0

    def _release(self, asset: Asset) -> None:
        self._pending.pop(asset, None)
        self._positions.pop(asset, None)
        self._stops.pop(asset, None)
        self._closing.discard(asset)
