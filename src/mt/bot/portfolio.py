from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from math import isfinite
from typing import Any, cast

from lumibot.entities import Order
from lumibot.strategies import Strategy as LumibotStrategy
from pandas import DataFrame, DatetimeIndex, Timedelta, Timestamp

from mt.data.asset import Asset, AssetType
from mt.data.broker import Broker, BrokerAlpaca, BrokerAsset, BrokerEngine
from mt.data.finnhub import stocks
from mt.exchange import TRADING_ZONE, midnight, session_bounds
from mt.frames import last_close, normalize_ohlcv
from mt.indicators import average_turnover_usd, daily_indicators
from mt.rules.bot import settings as bot_settings
from mt.rules.shared import settings
from mt.rules.values import OrderReason, StrategyKey
from mt.sizing import Direction, entry_quantity, round_quantity, round_stop
from mt.state import EventLevel
from mt.strategies.base import Candidate, Holding, Session, Strategy, ranked
from mt.strategies.daily import Daily
from mt.strategies.registry import STRATEGIES, liquidate_code, order_code

from .bars import Bars
from .export import StateExporter


@dataclass(slots=True)
class Pending:
    holding: Holding
    submitted_at: datetime
    notional_usd: float
    filled_quantity: float = 0.0
    filled_usd: float = 0.0


class Portfolio(LumibotStrategy):
    exporter: StateExporter | None = None

    def on_bot_crash(self, error: Exception) -> None:
        self._record("run.crashed", "error", type(error).__name__)

    def initialize(self) -> None:
        self.sleeptime = f"{bot_settings.portfolio.iteration_minutes}M"
        self.minutes_before_opening = bot_settings.portfolio.opening_lead_minutes
        selected = cast(list[StrategyKey], self.parameters["strategies"])
        given = cast(list[Asset] | None, self.parameters.get("assets"))
        self._broker: Broker = BrokerEngine(given) if given else BrokerAlpaca()
        self._bars = Bars()
        self._given = given
        self._benchmark = Asset.from_symbol(settings.benchmark_symbol)
        self._selected = set(selected)
        self._strategies: dict[StrategyKey, Strategy] = {cls.key: cls(self) for cls in STRATEGIES}
        self._holdings: dict[Asset, Holding] = {}
        self._pending: dict[Asset, Pending] = {}
        self._stops: dict[Asset, tuple[float, float]] = {}
        self._closing: set[Asset] = set()
        self._events: set[str] = set()
        self._traded: dict[StrategyKey, set[Asset]] = {cls.key: set() for cls in STRATEGIES}
        self._day: date | None = None
        self._session_baseline = 0.0
        self._locked_on: date | None = None
        self._daily_frames: dict[Asset, DataFrame] = {}
        self._assets: list[Asset] = []
        self._permissions: dict[Asset, BrokerAsset] = {}
        self._prepared_on: date | None = None

    def before_market_opens(self) -> None:
        self._prepare(self._now())

    def on_trading_iteration(self) -> None:
        now = self._now()
        bounds = session_bounds(now.date())
        if bounds is None:
            return
        opens, closes = bounds
        session = Session(now, opens, closes)
        self._begin_day(now.date())
        self._reconcile(now)
        if self._check_daily_loss(now.date()):
            return
        self._prepare(now)
        for holding in list(self._holdings.values()):
            if holding.asset not in self._pending and holding.asset not in self._closing:
                holding.strategy.manage(holding, session)
        for strategy in self._strategies.values():
            if not self._is_runnable(strategy):
                continue
            start, end = strategy.entry_window(session.opens, session.closes)
            if start <= now <= end:
                strategy.run(session)

    def before_market_closes(self) -> None:
        for holding in list(self._holdings.values()):
            if holding.strategy.is_stop_resting:
                self.exit(holding, "close")

    def on_partially_filled_order(
        self,
        engine_position: Any,
        order: Any,
        price: float,
        quantity: float | int,
        multiplier: float,
    ) -> None:
        self._fill(engine_position, order, price, quantity, is_complete=False)

    def on_filled_order(
        self,
        engine_position: Any,
        order: Any,
        price: float,
        quantity: float | int,
        multiplier: float,
    ) -> None:
        self._fill(engine_position, order, price, quantity, is_complete=True)

    def _fill(
        self,
        engine_position: Any,
        order: Any,
        price: float,
        quantity: float | int,
        *,
        is_complete: bool,
    ) -> None:
        asset = Asset.from_lumibot(order.asset)
        pending = self._pending.get(asset)
        if pending is not None and (
            order.is_buy_order() if pending.holding.direction == 1 else order.is_sell_order()
        ):
            holding = pending.holding
            is_first_fill = pending.filled_quantity == 0
            filled = abs(float(quantity))
            pending.filled_quantity += filled
            pending.filled_usd += filled * price
            holding.entry = pending.filled_usd / pending.filled_quantity
            if not holding.strategy.is_stop_resting:
                holding.tighten_stop(
                    holding.entry - holding.direction * holding.stop_distance, holding.stop_reason
                )
            holding.highest = price if is_first_fill else max(holding.highest, price)
            holding.lowest = price if is_first_fill else min(holding.lowest, price)
            holding.ladder = holding.strategy.ladder(holding, pending.filled_quantity)
            self._holdings[asset] = holding
            pending.notional_usd = max(0.0, pending.notional_usd - filled * price)
            if is_complete:
                self._pending.pop(asset)
            if self._is_locked():
                self._liquidate()
            elif holding.strategy.is_stop_resting:
                self.protect(holding, abs(float(engine_position.quantity)))
            return
        if is_complete:
            self._closing.discard(asset)
        held = self._holdings.get(asset)
        remaining = 0.0 if held is None else self._held(held)
        if held is None or remaining <= 0:
            self._release(asset)
        elif is_complete:
            self.protect(held, remaining)

    def assets(self) -> list[Asset]:
        return self._assets

    def daily_frame(self, asset: Asset) -> DataFrame | None:
        return self._daily_frames.get(asset)

    def frames(
        self, assets: list[Asset], start: datetime, now: datetime, minutes: int
    ) -> dict[Asset, DataFrame]:
        timeframe = f"{minutes // 60}Hour" if minutes % 60 == 0 else f"{minutes}Min"
        frames = self._bars.bars(assets, timeframe, start, now)
        return {asset: self._completed(frame, now, minutes) for asset, frame in frames.items()}

    def quote(self, asset: Asset) -> float | None:
        if self.is_backtesting:
            price = self.get_last_price(asset.to_lumibot())
            value = None if price is None else float(price)
        else:
            value = self._bars.quotes([asset], self._now()).get(asset)
        return value if value is not None and isfinite(value) and value > 0 else None

    def holding_count(self, key: StrategyKey) -> int:
        held = sum(1 for holding in self._holdings.values() if holding.strategy.key == key)
        ordered = sum(
            1
            for asset, pending in self._pending.items()
            if pending.holding.strategy.key == key and asset not in self._holdings
        )
        return held + ordered

    def is_taken(self, strategy: Strategy, asset: Asset) -> bool:
        is_owned = (
            asset in self._pending
            or asset in self._holdings
            or asset in self._positions(is_refreshed=False)
        )
        return is_owned or asset in self._traded[strategy.key]

    def record(self, strategy: Strategy, kind: str, level: EventLevel, message: str) -> None:
        self._record(f"{strategy.key}.{kind}", level, message, strategy.key)

    def _is_runnable(self, strategy: Strategy) -> bool:
        return strategy.key in self._selected and not strategy.is_paused

    def _now(self) -> datetime:
        return self.get_datetime().astimezone(TRADING_ZONE)

    def _is_locked(self) -> bool:
        return self._locked_on == self._now().date()

    def _submit(
        self,
        asset: Asset,
        quantity: float | Decimal,
        direction: Direction,
        code: str,
        **params: object,
    ) -> bool:
        order = self.create_order(
            asset.to_lumibot(),
            quantity,
            "buy" if direction == 1 else "sell",
            time_in_force="day",
            custom_params={"client_order_id": code},
            **params,
        )
        try:
            self.submit_order(order)
        except Exception as error:
            self._record(
                f"order.rejected.{asset}.{self._now().date()}",
                "warning",
                f"{asset} order rejected: {type(error).__name__}",
            )
            return False
        return True

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
        self._record(
            "feed.announced",
            "info",
            f"Intraday bars come from the broker's {settings.bars.intraday_feed} feed",
        )
        for strategy in self._strategies.values():
            self._traded[strategy.key].clear()
            strategy.begin(session_on=day)
            if strategy.key in self._selected and strategy.is_paused:
                self._record(
                    f"strategy.paused.{strategy.key}",
                    "warning",
                    f"{strategy.name()} is paused: no new entries",
                    strategy.key,
                )

    def _check_daily_loss(self, day: date) -> bool:
        if self._locked_on != day:
            if self._equity() > self._session_baseline * (1.0 - settings.risk.per_day_max):
                return False
            self._locked_on = day
            if self.is_backtesting:
                self.cancel_open_orders()
                self._closing.clear()
            self._stops.clear()
            self._record("day.locked", "warning", "Daily loss limit reached")
        if not self.is_backtesting:
            self._closing = self._broker.cancel_orders()
        self._liquidate()
        return True

    def _liquidate(self) -> None:
        for asset, quantity in self._positions().items():
            if asset not in self._closing:
                self._close(asset, quantity)

    def _close(self, asset: Asset, quantity: float) -> None:
        self._closing.add(asset)
        if not self._submit(asset, abs(quantity), -1 if quantity > 0 else 1, liquidate_code()):
            self._closing.discard(asset)

    def _tracked(self, *, is_refreshed: bool = True) -> list[Any]:
        return cast(list[Any], self.get_positions(broker_refresh=is_refreshed))

    def _positions(self, *, is_refreshed: bool = True) -> dict[Asset, float]:
        quantities = {
            Asset.from_lumibot(position.asset): float(position.quantity)
            for position in self._tracked(is_refreshed=is_refreshed)
        }
        return {asset: quantity for asset, quantity in quantities.items() if quantity}

    def _held(self, holding: Holding) -> float:
        return max(0.0, holding.direction * self._positions().get(holding.asset, 0.0))

    def _gross(self) -> float:
        return sum(abs(self._exposure(position)) for position in self._tracked())

    def _exposure(self, position: Any) -> float:
        market_value = getattr(position, "market_value", None)
        if market_value is not None:
            return float(market_value)
        return float(position.quantity) * float(self.get_last_price(position.asset))

    def _reconcile(self, now: datetime) -> None:
        positions = self._positions()
        for asset in list(self._holdings):
            if asset not in positions:
                self._release(asset)
        orders = cast(list[Any], self.get_orders(statuses=Order.ACTIVE_STATUSES))
        active = {Asset.from_lumibot(order.asset) for order in orders}
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
        owned = self._holdings.keys() | self._pending.keys() | self._closing
        for asset in active - positions.keys() - owned:
            self._cancel(asset, orders=orders)
        for asset in self._strays(positions, owned):
            self._record(
                f"position.stray.{asset}.{now.date()}",
                "warning",
                f"{asset} is held without a strategy holding: closing at market",
            )
            self._cancel(asset, orders=orders)
            self._close(asset, positions[asset])
        if self._locked_on != now.date():
            self._resync_stops(positions)

    def _strays(self, positions: dict[Asset, float], owned: set[Asset]) -> set[Asset]:
        strays = positions.keys() - owned
        return strays - self._broker.ordered(positions) if strays else strays

    def _resync_stops(self, positions: dict[Asset, float]) -> None:
        for asset, holding in self._holdings.items():
            if not holding.strategy.is_stop_resting or asset in self._closing:
                continue
            quantity = holding.direction * positions.get(asset, 0.0)
            if quantity <= 0:
                continue
            ladder = holding.ladder
            if ladder is not None and ladder.stage == 0:
                ladder.original_quantity = max(ladder.original_quantity, quantity)
            resting = self._stops.get(asset)
            drift_max = bot_settings.portfolio.stop_coverage_drift_max
            if resting is None or resting[1] < quantity - drift_max:
                self.protect(holding, quantity)

    def _prepare(self, now: datetime) -> None:
        day = now.date()
        if self._prepared_on == day:
            return
        first = day - timedelta(days=bot_settings.portfolio.lookback_days)
        start = midnight(first)
        self._permissions = self._broker.assets()
        assets = self._given or self._universe(now)
        fixed = {
            Asset.from_symbol(symbol)
            for strategy in self._strategies.values()
            if strategy.key in self._selected
            for symbol in strategy.symbols()
        }
        requested = sorted(
            set(assets).union({self._benchmark}, self._holdings, fixed),
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
                    frames[asset] = normalize_ohlcv(
                        bars.pandas_df, {"high", "low", "close", "volume"}
                    )
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
        self._prepared_on = day
        for strategy in self._strategies.values():
            if self._is_runnable(strategy):
                strategy.prepare(now)

    def _universe(self, now: datetime) -> list[Asset]:
        common_stocks = stocks()
        assets = sorted(
            (
                asset
                for asset in self._permissions
                if asset.asset_type == AssetType.STOCK and asset.symbol in common_stocks
            ),
            key=str,
        )
        first = now.date() - timedelta(days=settings.universe.lookback_days)
        start = midnight(first)
        frames = self._bars.bars(assets, "1Day", start, now)
        cleared: dict[Asset, float] = {}
        for asset, frame in frames.items():
            completed = self._completed(frame, now)
            if completed.empty or last_close(completed) <= settings.universe.price_usd_min:
                continue
            turnover = average_turnover_usd(completed, settings.universe.turnover_sessions)
            if turnover > settings.universe.turnover_usd_min:
                cleared[asset] = turnover
        return ranked(cleared, symbol=str, score=lambda asset: cleared[asset])

    def _completed(self, frame: DataFrame, now: datetime, minutes: int = 0) -> DataFrame:
        index = frame.index
        if not isinstance(index, DatetimeIndex):
            raise TypeError("bar frames must use a DatetimeIndex")
        if minutes:
            return frame.loc[: Timestamp(now) - Timedelta(minutes=minutes)]
        return frame[index < Timestamp(midnight(now.date()))]

    def enter(self, strategy: Strategy, candidate: Candidate, session: Session) -> bool:
        now = session.now
        asset, price, stop = candidate.asset, candidate.price, candidate.stop
        direction = candidate.direction
        positions = self._positions()
        owned = positions.keys() | self._pending.keys()
        if (
            asset.asset_type != AssetType.STOCK
            or not self._is_runnable(strategy)
            or asset in owned
            or asset in self._holdings
        ):
            return False
        if direction * (price - stop) <= 0:
            self.record(
                strategy,
                f"stop.rejected.{asset}.{now.date()}",
                "warning",
                f"{asset} entry skipped: stop is not beyond the entry price",
            )
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
        if len(owned) >= settings.risk.positions_max:
            self.record(
                strategy,
                f"portfolio.capped.{asset}.{now.date()}",
                "warning",
                f"{asset} entry skipped: portfolio holding capacity reached",
            )
            return False
        equity = self._equity()
        gross = self._gross() + sum(pending.notional_usd for pending in self._pending.values())
        quantity = entry_quantity(equity, price, abs(price - stop), direction)
        notional_usd = float(quantity) * price
        if quantity <= 0 or gross + notional_usd > equity:
            self.record(
                strategy,
                f"size.rejected.{asset}.{now.date()}",
                "warning",
                f"{asset} entry skipped: no affordable holding size",
            )
            return False
        holding = Holding(
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
        self._pending[asset] = Pending(holding, now, notional_usd)
        self._traded[strategy.key].add(asset)
        if not self._submit(asset, quantity, direction, order_code(strategy.code, "entry")):
            self._pending.pop(asset, None)
            return False
        return True

    def protect(self, holding: Holding, quantity: float | None = None) -> None:
        if (
            holding.asset in self._closing
            or not holding.strategy.is_stop_resting
            or self._is_locked()
        ):
            return
        held = self._held(holding)
        amount = held if quantity is None else min(quantity, held)
        price = self.quote(holding.asset)
        if price is None:
            return
        stop = round_stop(holding.direction, holding.stop)
        if amount <= 0 or stop <= 0:
            self.record(
                holding.strategy,
                f"stop.unplaced.{holding.asset}.{holding.entered_at.date()}",
                "warning",
                f"{holding.asset} has no resting stop yet: quantity or stop price is not positive",
            )
            return
        if (holding.direction == 1 and stop >= price) or (
            holding.direction == -1 and stop <= price
        ):
            self.record(
                holding.strategy,
                f"stop.passed.{holding.asset}.{holding.entered_at.date()}",
                "warning",
                f"{holding.asset} is already through its stop at {price:.2f}: closing at market",
            )
            self.exit(holding, holding.stop_reason)
            return
        size = round_quantity(amount)
        if size <= 0 or self._stops.get(holding.asset) == (stop, float(size)):
            return
        self._cancel(holding.asset, is_stop_only=True)
        if self._submit(
            holding.asset,
            size,
            -holding.direction,
            order_code(holding.strategy.code, holding.stop_reason),
            stop_price=stop,
        ):
            self._stops[holding.asset] = (stop, float(size))

    def exit(self, holding: Holding, reason: OrderReason, quantity: float | None = None) -> None:
        if holding.asset in self._closing:
            return
        current = self._held(holding)
        amount = current if quantity is None else min(quantity, current)
        if amount <= 0:
            self._release(holding.asset)
            return
        size = round_quantity(amount, is_whole=holding.direction == -1 and quantity is not None)
        if size <= 0:
            return
        self._cancel(holding.asset)
        self._closing.add(holding.asset)
        if not self._submit(
            holding.asset, size, -holding.direction, order_code(holding.strategy.code, reason)
        ):
            self._closing.discard(holding.asset)

    def _cancel(
        self,
        asset: Asset,
        *,
        is_stop_only: bool = False,
        orders: list[Any] | None = None,
    ) -> None:
        def matches(order: Any) -> bool:
            if Asset.from_lumibot(order.asset) != asset:
                return False
            return not is_stop_only or bool(order.is_stop_order())

        source = (
            orders
            if orders is not None
            else cast(list[Any], self.get_orders(statuses=Order.ACTIVE_STATUSES))
        )
        matched = [order for order in source if matches(order)]
        self.cancel_open_orders(matched)
        if matched and not self.is_backtesting:
            self.sleep(1)
        self._stops.pop(asset, None)

    def _release(self, asset: Asset) -> None:
        self._pending.pop(asset, None)
        self._holdings.pop(asset, None)
        self._stops.pop(asset, None)
        self._closing.discard(asset)
