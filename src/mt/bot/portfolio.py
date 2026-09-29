from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from math import isfinite
from typing import Any, cast

from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from lumibot.entities import Order
from lumibot.strategies import Strategy as LumibotStrategy
from pandas import DataFrame, Timedelta, Timestamp

from mt.data.asset import Asset, AssetType
from mt.data.broker import Broker, BrokerAlpaca, BrokerAsset, BrokerEngine
from mt.data.finnhub import stocks
from mt.exchange import TRADING_ZONE, midnight, session_bounds
from mt.frames import last_close, normalize_ohlcv, ranked
from mt.indicators import average_turnover_usd, daily_indicators
from mt.rules.bot import settings as bot_settings
from mt.rules.shared import settings
from mt.rules.values import OrderReason, StrategyKey
from mt.sizing import Direction, entry_quantity, round_quantity, round_stop
from mt.state import EventLevel
from mt.strategies.base import Candidate, Holding, Session, Strategy
from mt.strategies.daily import Daily
from mt.strategies.registry import STRATEGIES, liquidate_code, order_code

from .bars import Bars
from .export import StateExporter


DAILY_TIMEFRAME = TimeFrame(1, TimeFrameUnit("Day"))


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
        self._session_on: date | None = None
        self._session_baseline_usd = 0.0
        self._locked_on: date | None = None
        self._daily_frames: dict[Asset, DataFrame] = {}
        self._assets: list[Asset] = []
        self._permissions: dict[Asset, BrokerAsset] = {}
        self._prepared_on: date | None = None

    def before_market_opens(self) -> None:
        self._prepare(self._now())

    def on_trading_iteration(self) -> None:
        now_at = self._now()
        session_on = now_at.date()
        bounds = session_bounds(session_on)
        if bounds is None:
            return
        opens_at, closes_at = bounds
        session = Session(now_at, opens_at, closes_at)
        self._begin_day(session)
        self._reconcile(now_at)
        if self._is_day_locked():
            self._enforce_daily_loss()
            return
        self._prepare(now_at)
        for holding in list(self._holdings.values()):
            if holding.asset in self._pending or holding.asset in self._closing:
                continue
            if not holding.strategy.is_stop_resting and self._is_through_stop(holding):
                self.exit(holding, holding.stop_reason)
                continue
            holding.strategy.manage(holding, session)
        for strategy in self._strategies.values():
            if not self._is_runnable(strategy):
                continue
            start_at, end_at = strategy.entry_window(session.opens_at, session.closes_at)
            if start_at <= now_at <= end_at:
                strategy.run(session)

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

    def assets(self) -> list[Asset]:
        return self._assets

    def get_daily_frame(self, asset: Asset) -> DataFrame | None:
        return self._daily_frames.get(asset)

    def frames(
        self, assets: list[Asset], start_at: datetime, now_at: datetime, minutes: int
    ) -> dict[Asset, DataFrame]:
        frames = self._bars.bars(assets, _intraday_timeframe(minutes), start_at, now_at)
        return {
            asset: _completed_intraday(frame, now_at, minutes) for asset, frame in frames.items()
        }

    def quote(self, asset: Asset) -> float | None:
        if not self.is_backtesting:
            return self._bars.quotes([asset], self._now()).get(asset)
        price = self.get_last_price(asset.to_lumibot())
        return None if price is None or not isfinite(price) or price <= 0 else float(price)

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

    def enter(self, strategy: Strategy, candidate: Candidate, session: Session) -> None:
        session_on = session.now.date()
        asset, price, stop = candidate.asset, candidate.price, candidate.stop
        direction = candidate.direction
        if (
            asset.asset_type != AssetType.STOCK
            or not self._is_runnable(strategy)
            or asset in self._holdings
            or asset in self._pending
        ):
            return
        if direction * (price - stop) <= 0:
            self.record(
                strategy,
                f"stop.rejected.{asset}.{session_on}",
                "warning",
                f"{asset} entry skipped: stop is not beyond the entry price",
            )
            return
        if direction == -1 and (
            asset not in self._permissions or not self._permissions[asset].shortable
        ):
            self.record(
                strategy,
                f"short.refused.{asset}.{session_on}",
                "warning",
                f"Short entry skipped for {asset}: security is not shortable",
            )
            return
        tracked = self._tracked()
        owned = _quantities(tracked).keys() | self._pending.keys()
        if asset in owned:
            return
        if len(owned) >= settings.risk.positions_max:
            self.record(
                strategy,
                f"portfolio.capped.{asset}.{session_on}",
                "warning",
                f"{asset} entry skipped: portfolio holding capacity reached",
            )
            return
        equity_usd = self._equity()
        gross_usd = self._gross_usd(tracked) + sum(
            pending.notional_usd for pending in self._pending.values()
        )
        quantity = entry_quantity(equity_usd, price, abs(price - stop), direction)
        notional_usd = float(quantity) * price
        if quantity <= 0 or gross_usd + notional_usd > equity_usd:
            self.record(
                strategy,
                f"size.rejected.{asset}.{session_on}",
                "warning",
                f"{asset} entry skipped: no affordable holding size",
            )
            return
        holding = Holding(
            strategy,
            asset,
            direction,
            price,
            stop,
            abs(price - stop),
            session.now.astimezone(UTC),
            price,
            price,
        )
        self._pending[asset] = Pending(holding, session.now, notional_usd)
        self._traded[strategy.key].add(asset)
        if not self._try_submit(asset, quantity, direction, order_code(strategy.code, "entry")):
            self._pending.pop(asset, None)

    def protect(self, holding: Holding, quantity: float | None = None) -> None:
        if (
            holding.asset in self._closing
            or not holding.strategy.is_stop_resting
            or self._is_locked()
        ):
            return
        held = self._held(holding)
        shares = held if quantity is None else min(quantity, held)
        stop = round_stop(holding.direction, holding.stop)
        if shares <= 0 or stop <= 0:
            self.record(
                holding.strategy,
                f"stop.unplaced.{holding.asset}.{holding.entered_at.date()}",
                "warning",
                f"{holding.asset} has no resting stop yet: quantity or stop price is not positive",
            )
            return
        price = self.quote(holding.asset)
        if price is None:
            return
        if holding.direction * (price - stop) <= 0:
            self.record(
                holding.strategy,
                f"stop.passed.{holding.asset}.{holding.entered_at.date()}",
                "warning",
                f"{holding.asset} is already through its stop at {price:.2f}: closing at market",
            )
            self.exit(holding, holding.stop_reason)
            return
        order_shares = round_quantity(shares)
        if order_shares <= 0 or self._stops.get(holding.asset) == (stop, float(order_shares)):
            return
        self._cancel(holding.asset, is_stop_only=True)
        if self._try_submit(
            holding.asset,
            order_shares,
            -holding.direction,
            order_code(holding.strategy.code, holding.stop_reason),
            stop_price=stop,
        ):
            self._stops[holding.asset] = (stop, float(order_shares))

    def exit(self, holding: Holding, reason: OrderReason, quantity: float | None = None) -> None:
        if holding.asset in self._closing:
            return
        held = self._held(holding)
        shares = held if quantity is None else min(quantity, held)
        if shares <= 0:
            self._release(holding.asset)
            return
        order_shares = round_quantity(
            shares, is_whole=holding.direction == -1 and quantity is not None
        )
        if order_shares <= 0:
            return
        self._cancel(holding.asset)
        self._closing.add(holding.asset)
        if not self._try_submit(
            holding.asset,
            order_shares,
            -holding.direction,
            order_code(holding.strategy.code, reason),
        ):
            self._closing.discard(holding.asset)

    def record(self, strategy: Strategy, kind: str, level: EventLevel, message: str) -> None:
        self._record(f"{strategy.key}.{kind}", level, message, strategy.key)

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
            filled = abs(float(quantity))
            pending.filled_quantity += filled
            pending.filled_usd += filled * price
            holding.entry = pending.filled_usd / pending.filled_quantity
            if not holding.strategy.is_stop_resting:
                holding.tighten_stop(
                    holding.entry - holding.direction * holding.stop_distance, holding.stop_reason
                )
            holding.mark(price)
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

    def _is_runnable(self, strategy: Strategy) -> bool:
        return strategy.key in self._selected and not strategy.is_paused

    def _is_through_stop(self, holding: Holding) -> bool:
        price = self.quote(holding.asset)
        return price is not None and holding.direction * (price - holding.stop) <= 0

    def _now(self) -> datetime:
        return self.get_datetime().astimezone(TRADING_ZONE)

    def _is_locked(self) -> bool:
        return self._locked_on == self._now().date()

    def _try_submit(
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
            self.exporter.record("running", kind, level, message, strategy_key=strategy_key)

    def _equity(self) -> float:
        value = self.get_portfolio_value()
        if value is None:
            raise RuntimeError("portfolio value is unavailable")
        return float(value)

    def _begin_day(self, session: Session) -> None:
        session_on = session.now.date()
        if session_on == self._session_on:
            return
        self._session_on = session_on
        self._session_baseline_usd = self._equity()
        self._events.clear()
        self._record(
            "feed.announced",
            "info",
            f"Intraday bars come from the broker's {settings.bars.intraday_feed} feed",
        )
        for strategy in self._strategies.values():
            self._traded[strategy.key].clear()
            strategy.begin(session)
            if strategy.key in self._selected and strategy.is_paused:
                self._record(
                    f"strategy.paused.{strategy.key}",
                    "warning",
                    f"{strategy.name()} is paused: no new entries",
                    strategy.key,
                )

    def _is_day_locked(self) -> bool:
        if self._is_locked():
            return True
        return self._equity() <= self._session_baseline_usd * (1.0 - settings.risk.per_day_max)

    def _enforce_daily_loss(self) -> None:
        if not self._is_locked():
            self._locked_on = self._now().date()
            if self.is_backtesting:
                self.cancel_open_orders()
                self._closing.clear()
            self._stops.clear()
            self._record("day.locked", "warning", "Daily loss limit reached")
        if not self.is_backtesting:
            self._closing = self._broker.cancel_orders()
        self._liquidate()

    def _liquidate(self) -> None:
        for asset, quantity in self._positions().items():
            if asset not in self._closing:
                self._close(asset, quantity)

    def _close(self, asset: Asset, quantity: float) -> None:
        self._closing.add(asset)
        if not self._try_submit(asset, abs(quantity), -1 if quantity > 0 else 1, liquidate_code()):
            self._closing.discard(asset)

    def _tracked(self, *, is_refreshed: bool = True) -> list[Any]:
        return cast(list[Any], self.get_positions(broker_refresh=is_refreshed))

    def _positions(self, *, is_refreshed: bool = True) -> dict[Asset, float]:
        return _quantities(self._tracked(is_refreshed=is_refreshed))

    def _held(self, holding: Holding) -> float:
        return max(0.0, holding.direction * self._positions().get(holding.asset, 0.0))

    def _gross_usd(self, tracked: list[Any]) -> float:
        return sum(abs(self._exposure(position)) for position in tracked)

    def _exposure(self, position: Any) -> float:
        market_value = getattr(position, "market_value", None)
        if market_value is not None:
            return float(market_value)
        return float(position.quantity) * float(self.get_last_price(position.asset))

    def _reconcile(self, now_at: datetime) -> None:
        positions = self._positions()
        for asset in list(self._holdings):
            if asset not in positions:
                self._release(asset)
        orders = cast(list[Any], self.get_orders(statuses=Order.ACTIVE_STATUSES))
        active = {Asset.from_lumibot(order.asset) for order in orders}
        ttl = timedelta(minutes=bot_settings.portfolio.pending_ttl_minutes)
        for asset, pending in list(self._pending.items()):
            is_expired = now_at - pending.submitted_at > ttl
            if asset not in active and is_expired:
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
                f"position.stray.{asset}.{now_at.date()}",
                "warning",
                f"{asset} is held without a strategy holding: closing at market",
            )
            self._cancel(asset, orders=orders)
            self._close(asset, positions[asset])
        if not self._is_locked():
            self._resync_stops(positions)

    def _strays(self, positions: dict[Asset, float], owned: set[Asset]) -> set[Asset]:
        strays = positions.keys() - owned
        return strays - self._broker.find_closing_assets(positions) if strays else strays

    def _resync_stops(self, positions: dict[Asset, float]) -> None:
        drift_shares_max = bot_settings.portfolio.stop_coverage_drift_shares_max
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
            if resting is None or resting[1] < quantity - drift_shares_max:
                self.protect(holding, quantity)

    def _prepare(self, now_at: datetime) -> None:
        session_on = now_at.date()
        if self._prepared_on == session_on:
            return
        self._permissions = self._broker.assets()
        candidates = self._given or self._find_stocks()
        requested = list({*candidates, self._benchmark, *self._holdings})
        completed = {
            asset: _completed_daily(frame, now_at)
            for asset, frame in self._get_daily_bars(requested, now_at).items()
        }
        self._assets = list(self._given or self._universe(candidates, completed, session_on))
        lengths = {
            length
            for strategy in self._strategies.values()
            if isinstance(strategy, Daily) and strategy.key in self._selected
            for length in strategy.sma_lengths()
        }
        kept = {*self._assets, self._benchmark, *self._holdings}
        self._daily_frames = {
            asset: daily_indicators(frame, lengths, settings.indicators.period_bars)
            for asset, frame in completed.items()
            if asset in kept
        }
        self._prepared_on = session_on

    def _find_stocks(self) -> list[Asset]:
        common_stocks = stocks()
        return [
            asset
            for asset in self._permissions
            if asset.asset_type == AssetType.STOCK and asset.symbol in common_stocks
        ]

    def _get_daily_bars(self, assets: list[Asset], now_at: datetime) -> dict[Asset, DataFrame]:
        lookback_days = max(bot_settings.portfolio.lookback_days, settings.universe.lookback_days)
        if not self.is_backtesting or any(
            not isinstance(self._strategies[key], Daily) for key in self._selected
        ):
            return self._bars.bars(
                assets,
                DAILY_TIMEFRAME,
                midnight(now_at.date() - timedelta(days=lookback_days)),
                now_at,
            )
        frames: dict[Asset, DataFrame] = {}
        for asset in assets:
            bars = self.get_historical_prices(
                asset.to_lumibot(), bot_settings.portfolio.lookback_days, timestep="day"
            )
            if bars is not None:
                frames[asset] = normalize_ohlcv(bars.pandas_df, {"high", "low", "close", "volume"})
        return frames

    def _universe(
        self, candidates: list[Asset], completed: dict[Asset, DataFrame], session_on: date
    ) -> list[Asset]:
        start_at = midnight(session_on - timedelta(days=settings.universe.lookback_days))
        cleared: dict[Asset, float] = {}
        for asset in candidates:
            frame = completed[asset].loc[start_at:]
            if frame.empty or last_close(frame) <= settings.universe.price_usd_min:
                continue
            turnover = average_turnover_usd(frame, settings.universe.turnover_sessions)
            if turnover > settings.universe.turnover_usd_min:
                cleared[asset] = turnover
        return ranked(cleared, symbol=str, score=lambda asset: cleared[asset])

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


def _quantities(tracked: list[Any]) -> dict[Asset, float]:
    quantities = {
        Asset.from_lumibot(position.asset): float(position.quantity) for position in tracked
    }
    return {asset: quantity for asset, quantity in quantities.items() if quantity}


def _intraday_timeframe(minutes: int) -> TimeFrame:
    if minutes % 60 == 0:
        return TimeFrame(minutes // 60, TimeFrameUnit("Hour"))
    return TimeFrame(minutes, TimeFrameUnit("Min"))


def _completed_daily(frame: DataFrame, now_at: datetime) -> DataFrame:
    return frame[frame.index < Timestamp(midnight(now_at.date()))]


def _completed_intraday(frame: DataFrame, now_at: datetime, minutes: int) -> DataFrame:
    return frame.loc[: Timestamp(now_at) - Timedelta(minutes=minutes)]
