import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from importlib import import_module
from math import isfinite
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from alpaca.common.enums import Sort
from alpaca.data.enums import Adjustment, DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.trading.enums import QueryOrderStatus
from alpaca.trading.requests import GetOrdersRequest
from pandas import DataFrame, DatetimeIndex, Series, Timestamp

from bot.attribution import STRATEGY_CODES, find_order_strategy
from bot.config import settings
from bot.strategies.base import StrategyBase
from bot.strategies.orb_base import relative_volume_ready
from bot.strategies.shared import (
    TRADING_ZONE,
    Direction,
    does_macd_confirm,
    earnings_blocked,
    earnings_exit_due,
    entry_quantity,
    latest_atr,
    market_is_rising,
    momentum_entry,
    next_stop,
    normalize_ohlcv,
    quantity_value,
    signal_exit,
    tfb_entry,
)
from bot.types import STRATEGY_LABELS, EventLevel, StrategyName, active_strategies


FIVE_MINUTES = TimeFrame(5, cast(TimeFrameUnit, TimeFrameUnit.Minute))
TEN_MINUTES = TimeFrame(10, cast(TimeFrameUnit, TimeFrameUnit.Minute))
UNIVERSE_CACHE = Path("/tmp/money-tree-universe.json")
PREPARATION_ATTEMPTS_MAX = 2
STOP_COVERAGE_TOLERANCE = 1e-6


@dataclass(slots=True)
class Holding:
    engine: StrategyName
    signal: str
    asset: str
    entry: float
    stop: float
    risk: float
    highest: float
    entered_at: datetime
    stage: int = 0
    direction: Direction = 1
    original_quantity: float = 0.0
    targets: tuple[float, float, float] | None = None
    lowest: float = float("inf")


@dataclass(slots=True)
class Pending:
    holding: Holding
    submitted_at: datetime
    notional: float


@dataclass(frozen=True, slots=True)
class OrbCandidate:
    symbol: str
    direction: Direction
    high: float
    low: float
    close: float


class LoadUniverseError(Exception):
    pass


class Strategy(StrategyBase):
    def initialize(self) -> None:
        self.sleeptime = "1M"
        self.minutes_before_opening = 30
        selected = cast(list[StrategyName], self.parameters["strategies"])
        self._selected = selected
        self._enabled = set(active_strategies(selected))
        self._exit_only: set[StrategyName] = set(selected).difference(self._enabled)
        self._holdings: dict[str, Holding] = {}
        self._pending: dict[str, Pending] = {}
        self._claims: dict[str, StrategyName | None] = {}
        self._stops: dict[str, tuple[float, float]] = {}
        self._closing: set[str] = set()
        self._events: set[str] = set()
        self._orb_traded: set[tuple[date, str]] = set()
        self._orb_scanned: set[tuple[date, StrategyName, str]] = set()
        self._day: date | None = None
        self._baseline_equity = 0.0
        self._locked_on: date | None = None
        self._daily_frames: dict[str, DataFrame] = {}
        self._eligible_symbols: list[str] = []
        self._prepared_on: date | None = None
        self._preparation_attempts = 0
        self._preparation_attempts_on: date | None = None
        self._daily_run_on: date | None = None
        self._intraday_bucket: datetime | None = None
        self._restored = False
        api_key = settings.alpaca_api_key
        api_secret = settings.alpaca_api_secret
        if api_key is None or api_secret is None:
            raise RuntimeError("Alpaca credentials must be set")
        self._data = StockHistoricalDataClient(
            api_key.get_secret_value(), api_secret.get_secret_value()
        )

    def before_market_opens(self) -> None:
        self._restore()
        self._prepare(self.get_datetime().astimezone(TRADING_ZONE).date())

    def on_trading_iteration(self) -> None:
        now = self.get_datetime().astimezone(TRADING_ZONE)
        self._restore()
        self._begin_day(now.date())
        self._reconcile(now)
        if self._daily_loss_reached(now.date()):
            return
        self._prepare(now.date())
        self._manage(now)
        if self._daily_run_on != now.date() and now.time() < time(9, 40):
            self._run_daily(now)
        bucket = now.replace(second=0, microsecond=0)
        if now.minute % 5 == 0 and bucket != self._intraday_bucket:
            self._intraday_bucket = bucket
            self._run_orb(now)
            self._run_orb_momentum(now)

    def on_filled_order(
        self,
        position: Any,
        order: Any,
        price: float,
        quantity: float | int,
        multiplier: float,
    ) -> None:
        asset = str(order.asset.symbol)
        side = str(order.side).lower()
        pending = self._pending.get(asset)
        entry_side = "buy" if pending is None or pending.holding.direction == 1 else "sell"
        if pending is not None and entry_side in side:
            self._pending.pop(asset)
            holding = pending.holding
            holding.entry = self._entry_price(order, price)
            holding.risk = abs(holding.entry - holding.stop)
            holding.highest = holding.entry
            holding.lowest = holding.entry
            holding.original_quantity = self._entry_quantity_filled(asset, quantity)
            if holding.engine == "orb":
                holding.targets = cast(
                    tuple[float, float, float],
                    tuple(
                        holding.entry + holding.direction * holding.risk * multiple
                        for multiple in (1.5, 2.5, 4.0)
                    ),
                )
            self._holdings[asset] = holding
            if holding.engine in {"orb", "orb_momentum"}:
                self._protect(holding)
            return
        self._closing.discard(asset)
        remaining = abs(float(getattr(position, "quantity", 0.0)))
        if remaining <= 0:
            self._release(asset)
        elif asset in self._holdings:
            holding = self._holdings[asset]
            if holding.stage == 0:
                holding.original_quantity = max(holding.original_quantity, remaining)
            self._protect(holding, remaining)

    def _entry_price(self, order: Any, price: float) -> float:
        average = getattr(order, "avg_fill_price", None)
        try:
            value = float(average) if average is not None else 0.0
        except (TypeError, ValueError):
            value = 0.0
        return value if isfinite(value) and value > 0 else float(price)

    def _entry_quantity_filled(self, asset: str, reported: float | int) -> float:
        return max(self._quantity(asset), abs(float(reported)))

    def _event(
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
            label = None if strategy is None else STRATEGY_LABELS[strategy]
            self.exporter.publish("running", key, level, message, strategy=label)

    def _begin_day(self, day: date) -> None:
        if day == self._day:
            return
        account = self.broker.api.get_account()
        equity = float(account.portfolio_value)
        previous = float(account.last_equity)
        self._day = day
        self._baseline_equity = previous if previous > 0 else equity
        self._events.clear()
        self._intraday_bucket = None

    def _daily_loss_reached(self, day: date) -> bool:
        if self._locked_on == day:
            return True
        equity = float(self.broker.api.get_account().portfolio_value)
        limit = float(self.parameters["risk_per_day_max"])
        if equity > self._baseline_equity * (1.0 - limit):
            return False
        self.cancel_open_orders()
        for holding in list(self._holdings.values()):
            self._exit(holding)
        self._locked_on = day
        self._event("daily-loss", "warning", "Daily loss limit reached")
        return True

    def _restore(self) -> None:
        if self._restored:
            return
        for engine in sorted(self._exit_only):
            self._event(
                f"paused-{engine}",
                "warning",
                f"{engine} is paused: existing positions only, no new entries",
                engine,
            )
        request = GetOrdersRequest(status=QueryOrderStatus.ALL, limit=500, direction=Sort.DESC)
        orders = cast(list[Any], self.broker.api.get_orders(filter=request))
        positions = cast(list[Any], self.broker.api.get_all_positions())
        self._event("market-data", "info", "Intraday strategies use Alpaca IEX market data")
        for position in positions:
            asset = str(position.symbol)
            match = next(
                (
                    order
                    for order in orders
                    if str(order.symbol) == asset
                    and self._order_engine(str(order.client_order_id)) is not None
                ),
                None,
            )
            quantity = float(position.qty)
            if match is None or quantity == 0:
                self._claims[asset] = None
                continue
            engine = self._order_engine(str(match.client_order_id))
            if engine is None:
                continue
            entry_order = next(
                (
                    order
                    for order in orders
                    if str(order.symbol) == asset
                    and str(order.client_order_id).split("-")[2:3] == ["e"]
                    and self._order_engine(str(order.client_order_id)) == engine
                ),
                match,
            )
            client_order_id = str(entry_order.client_order_id)
            signal = self._order_signal(client_order_id) or asset
            entry = float(position.avg_entry_price)
            risk = entry * (self._order_risk(client_order_id) or 0.01)
            entered_at = entry_order.filled_at or datetime.now(UTC)
            direction: Direction = 1 if quantity > 0 else -1
            original = abs(float(entry_order.filled_qty or entry_order.qty or position.qty))
            targets: tuple[float, float, float] | None = None
            if engine == "orb":
                targets = cast(
                    tuple[float, float, float],
                    tuple(entry + direction * risk * value for value in (1.5, 2.5, 4.0)),
                )
            if engine == "orb_momentum":
                targets = cast(
                    tuple[float, float, float],
                    tuple(entry + direction * risk * value for value in (2.0, 4.0, 8.0)),
                )
            holding = Holding(
                engine,
                signal,
                asset,
                entry,
                entry - direction * risk,
                risk,
                entry,
                entered_at,
                direction=direction,
                original_quantity=original,
                targets=targets,
                lowest=entry,
            )
            remaining_fraction = abs(quantity) / original
            if engine in {"orb", "orb_momentum"} and remaining_fraction <= 0.5:
                holding.stage = 1 if remaining_fraction > 0.25 else 2
            self._holdings[asset] = holding
            self._claims[asset] = engine
            self._claims[signal] = engine
            if engine not in self._enabled:
                self._exit_only.add(engine)
                self._event(
                    f"exit-only-{engine}",
                    "warning",
                    f"{engine} is managing existing positions only",
                    engine,
                )
        self._restored = True

    def _reconcile(self, now: datetime) -> None:
        positions = {str(value.symbol): value for value in self.broker.api.get_all_positions()}
        for asset in list(self._holdings):
            if asset not in positions:
                self._release(asset)
        active = {
            str(order.asset.symbol)
            for order in cast(list[Any], self.get_orders())
            if order.is_active()
        }
        for asset, pending in list(self._pending.items()):
            expired = now - pending.submitted_at > timedelta(minutes=5)
            if asset not in positions and asset not in active and expired:
                self._release(asset)
        for asset in set(self._stops).difference(active):
            self._stops.pop(asset, None)
        self._closing.intersection_update(active)
        self._resync_stops(positions)

    def _resync_stops(self, positions: dict[str, Any]) -> None:
        for asset, holding in self._holdings.items():
            if holding.engine not in {"orb", "orb_momentum"} or asset in self._closing:
                continue
            position = positions.get(asset)
            if position is None:
                continue
            quantity = abs(float(position.qty))
            if quantity <= 0:
                continue
            if holding.stage == 0:
                holding.original_quantity = max(holding.original_quantity, quantity)
            resting = self._stops.get(asset)
            if resting is None or resting[1] < quantity - STOP_COVERAGE_TOLERANCE:
                self._protect(holding, quantity)

    def _prepare(self, day: date) -> None:
        if self._prepared_on == day:
            return
        if self._preparation_attempts_on != day:
            self._preparation_attempts_on = day
            self._preparation_attempts = 0
        if self._preparation_attempts >= PREPARATION_ATTEMPTS_MAX:
            return
        self._preparation_attempts += 1
        try:
            eligible = self._universe()
            held = {holding.signal for holding in self._holdings.values()}
            symbols = sorted(set(eligible).union({"SPY", "QQQ"}, held))
            daily_frames = self._frames(
                symbols,
                datetime.combine(day - timedelta(days=390), time(), TRADING_ZONE),
                cast(TimeFrame, TimeFrame.Day),
            )
            spx = self._spx(day)
            if spx is not None:
                daily_frames["^GSPC"] = spx
        except Exception as error:
            self._daily_frames = {}
            self._eligible_symbols = []
            self._event("universe", "error", f"Stock universe unavailable: {error}")
            return
        self._daily_frames = daily_frames
        self._eligible_symbols = eligible
        self._prepared_on = day

    def _spx(self, day: date) -> DataFrame | None:
        try:
            finance = cast(Any, import_module("yfinance"))
            frame = finance.Ticker("^GSPC").history(
                start=day - timedelta(days=390),
                end=day + timedelta(days=1),
                auto_adjust=True,
            )
            if frame.empty:
                return None
            frame = cast(DataFrame, frame).rename(
                columns={column: str(column).lower() for column in frame.columns}
            )
            return normalize_ohlcv(frame, {"close"})
        except Exception as error:
            self._event("spx", "error", f"SPX market state unavailable: {type(error).__name__}")
            return None

    def _universe(self) -> list[str]:
        try:
            eligible = self._discover_eligible_symbols()
            self._write_universe_cache(eligible)
            return eligible
        except Exception as discovery_error:
            try:
                return self._load_universe_cache()
            except Exception as cache_error:
                message = (
                    f"live discovery failed with {type(discovery_error).__name__}; "
                    f"cache {UNIVERSE_CACHE} failed with {type(cache_error).__name__}"
                )
                raise LoadUniverseError(message) from ExceptionGroup(
                    "universe loading failed",
                    [discovery_error, cache_error],
                )

    def _discover_eligible_symbols(self) -> list[str]:
        finance = cast(Any, import_module("yfinance"))
        Query = finance.EquityQuery
        query = Query(
            "and",
            [
                Query("eq", ["region", "us"]),
                Query("gte", ["intradaymarketcap", 500_000_000]),
            ],
        )
        quotes: list[dict[str, Any]] = []
        offset = 0
        while True:
            page = finance.screen(
                query,
                offset=offset,
                size=250,
                sortField="intradaymarketcap",
                sortAsc=False,
            )
            values = cast(list[dict[str, Any]], page.get("quotes", []))
            quotes.extend(values)
            offset += len(values)
            if not values or offset >= int(page.get("total", offset)):
                break
        assets = {
            str(asset.symbol)
            for asset in self.broker.api.get_all_assets()
            if bool(asset.tradable) and bool(asset.fractionable)
        }
        rows = [
            (
                str(value.get("symbol", "")).replace("-", "."),
                float(value.get("marketCap") or 0),
                float(value.get("averageDailyVolume3Month") or 0),
            )
            for value in quotes
            if value.get("quoteType") == "EQUITY"
        ]
        return sorted(
            {
                symbol
                for symbol, cap, volume in rows
                if symbol in assets and cap >= 5e8 and volume >= 1e6
            }
        )

    def _load_universe_cache(self) -> list[str]:
        cached: object = json.loads(UNIVERSE_CACHE.read_text())
        if not isinstance(cached, dict):
            raise ValueError("universe cache must be an eligible-symbol object")
        payload = cast(dict[str, object], cached)
        if set(payload) != {"eligible"}:
            raise ValueError("universe cache must be an eligible-symbol object")
        symbols = payload["eligible"]
        if not isinstance(symbols, list):
            raise ValueError("universe cache eligible symbols must be non-empty strings")
        loaded: set[str] = set()
        for symbol in cast(list[object], symbols):
            if not isinstance(symbol, str) or not symbol.strip():
                raise ValueError("universe cache eligible symbols must be non-empty strings")
            loaded.add(symbol.strip())
        return sorted(loaded)

    def _write_universe_cache(self, symbols: list[str]) -> None:
        temporary = UNIVERSE_CACHE.with_name(f".{UNIVERSE_CACHE.name}.{uuid4().hex}.tmp")
        try:
            temporary.write_text(json.dumps({"eligible": symbols}))
            temporary.replace(UNIVERSE_CACHE)
        finally:
            temporary.unlink(missing_ok=True)

    def _frames(
        self, symbols: list[str], start: datetime, timeframe: TimeFrame, end: datetime | None = None
    ) -> dict[str, DataFrame]:
        frames: dict[str, DataFrame] = {}
        for offset in range(0, len(symbols), 50):
            request = StockBarsRequest(
                symbol_or_symbols=symbols[offset : offset + 50],
                start=start.astimezone(UTC),
                end=None if end is None else end.astimezone(UTC),
                timeframe=timeframe,
                adjustment=Adjustment.ALL,
                feed=DataFeed.IEX,
            )
            values = cast(DataFrame, cast(Any, self._data.get_stock_bars(request)).df)
            if values.empty:
                continue
            symbols_index = cast(
                list[object],
                cast(Any, values.index).get_level_values("symbol").unique().tolist(),
            )
            for symbol_value in symbols_index:
                symbol = str(symbol_value)
                frame = values.xs(symbol_value, level="symbol")
                frames[symbol] = normalize_ohlcv(
                    frame,
                    {"high", "low", "close", "volume"},
                )
        return frames

    def _completed(self, frame: DataFrame, now: datetime, minutes: int = 0) -> DataFrame:
        index = cast(DatetimeIndex, frame.index)
        if minutes:
            mask = cast(Any, index) + timedelta(minutes=minutes) <= now
            return cast(DataFrame, frame[mask])
        return cast(DataFrame, frame[cast(Any, index).date < now.date()])

    def _run_daily(self, now: datetime) -> None:
        market_frame = self._daily_frames.get("^GSPC")
        if market_frame is None:
            return
        market = self._completed(market_frame, now)
        if not market_is_rising(market):
            self._event("market-state", "warning", "SPX is not above its 20-day average")
            self._daily_run_on = now.date()
            return
        for engine in self._selected:
            if engine not in self._enabled:
                continue
            if engine == "sma":
                self._run_sma(now)
            if engine == "tfb_50":
                self._run_tfb(now)
        self._daily_run_on = now.date()

    def _run_sma(self, now: datetime) -> None:
        for symbol in self._eligible_symbols:
            daily_frame = self._daily_frames.get(symbol)
            if daily_frame is None:
                continue
            frame = self._completed(daily_frame, now)
            if self._claimed(symbol) or not momentum_entry(frame):
                continue
            try:
                blocked = earnings_blocked(symbol, now.date())
            except Exception as error:
                self._event(
                    f"earnings-{symbol}",
                    "error",
                    f"Earnings calendar unavailable for {symbol}: {type(error).__name__}",
                    "sma",
                )
                continue
            if blocked:
                continue
            last = float(cast(Any, frame["close"]).iloc[-1])
            self._enter("sma", symbol, symbol, last, last - 1.5 * latest_atr(frame), now)

    def _run_tfb(self, now: datetime) -> None:
        for symbol in self._eligible_symbols:
            daily_frame = self._daily_frames.get(symbol)
            if daily_frame is None:
                continue
            frame = self._completed(daily_frame, now)
            if self._claimed(symbol) or not tfb_entry(frame):
                continue
            last = float(cast(Any, frame["close"]).iloc[-1])
            self._enter("tfb_50", symbol, symbol, last, last - 2.0 * latest_atr(frame), now)

    def _run_orb(self, now: datetime) -> None:
        self._run_orb_variant("orb", now, 5, 1.3, False)

    def _run_orb_momentum(self, now: datetime) -> None:
        self._run_orb_variant("orb_momentum", now, 10, 1.5, True)

    def _run_orb_variant(
        self,
        engine: StrategyName,
        now: datetime,
        minutes: int,
        volume_multiple: float,
        uses_macd: bool,
    ) -> None:
        opening_end = time(9, 35) if minutes == 5 else time(9, 40)
        if (
            engine not in self._enabled
            or now.minute % minutes
            or not opening_end <= now.time() <= time(10, 30)
            or not self._eligible_symbols
        ):
            return
        frames = self._intraday(self._eligible_symbols, now, minutes)
        candidates: list[OrbCandidate] = []
        for symbol in self._eligible_symbols:
            key = (now.date(), engine, symbol)
            frame = frames.get(symbol)
            if key in self._orb_scanned or frame is None or frame.empty or self._claimed(symbol):
                continue
            opening = cast(
                DataFrame,
                cast(Any, frame).between_time("09:30", "09:34" if minutes == 5 else "09:39"),
            )
            candle = cast(Series, cast(Any, frame).iloc[-1])
            frame_at = cast(Timestamp, frame.index[-1])
            if opening.empty or frame_at.time() < opening_end:
                continue
            high = float(cast(Any, opening["high"]).max())
            low = float(cast(Any, opening["low"]).min())
            close = float(cast(Any, candle)["close"])
            if not all(isfinite(value) for value in (high, low, close)):
                continue
            direction: Direction | None = 1 if close > high else -1 if close < low else None
            if direction is None:
                continue
            self._orb_scanned.add(key)
            candidates.append(OrbCandidate(symbol, direction, high, low, close))
        if not candidates:
            return
        timeframe = FIVE_MINUTES if minutes == 5 else TEN_MINUTES
        histories = self._frames(
            [candidate.symbol for candidate in candidates],
            now - timedelta(days=45),
            timeframe,
            now,
        )
        for candidate in candidates:
            frame = histories.get(candidate.symbol)
            if frame is None:
                continue
            completed = self._completed(frame, now, minutes)
            if not self._orb_confirm(
                completed,
                now,
                volume_multiple,
                candidate.direction,
                uses_macd,
            ):
                continue
            span = candidate.high - candidate.low
            stop = candidate.low + span * (0.75 if candidate.direction == 1 else 0.25)
            targets = None
            if minutes == 10:
                targets = (
                    (
                        candidate.high + 0.5 * span,
                        candidate.high + span,
                        candidate.high + 2.0 * span,
                    )
                    if candidate.direction == 1
                    else (
                        candidate.low - 0.5 * span,
                        candidate.low - span,
                        candidate.low - 2.0 * span,
                    )
                )
            self._enter(
                engine,
                candidate.symbol,
                candidate.symbol,
                candidate.close,
                stop,
                now,
                direction=candidate.direction,
                targets=targets,
                risk_fraction_max=0.01 if engine == "orb" else None,
            )

    def _intraday(self, symbols: list[str], now: datetime, minutes: int) -> dict[str, DataFrame]:
        start = datetime.combine(now.date(), time(9, 30), TRADING_ZONE)
        timeframe = FIVE_MINUTES if minutes == 5 else TEN_MINUTES
        return {
            symbol: self._completed(frame, now, minutes)
            for symbol, frame in self._frames(symbols, start, timeframe, now).items()
        }

    def _orb_confirm(
        self,
        frame: DataFrame,
        now: datetime,
        volume_multiple: float,
        direction: Direction,
        uses_macd: bool,
    ) -> bool:
        if frame.empty:
            return False
        if not relative_volume_ready(
            frame,
            now.date(),
            cast(Timestamp, frame.index[-1]).time(),
            volume_multiple,
        ):
            return False
        if not uses_macd:
            return True
        regular = cast(DataFrame, cast(Any, frame).between_time("09:30", "15:59"))
        return does_macd_confirm(cast(Series, regular["close"]), direction)

    def _manage(self, now: datetime) -> None:
        for holding in list(self._holdings.values()):
            if now.time() >= time(15, 55) and holding.engine in {"orb", "orb_momentum"}:
                self._exit(holding)
                continue
            if holding.engine in {"sma", "tfb_50"}:
                self._manage_daily(holding, now)
            else:
                self._manage_orb(holding, now)

    def _manage_daily(self, holding: Holding, now: datetime) -> None:
        try:
            exit_for_earnings = earnings_exit_due(holding.signal, now.date())
        except Exception as error:
            self._event(
                f"earnings-{holding.signal}",
                "error",
                f"Earnings calendar unavailable for {holding.signal}: {type(error).__name__}",
                holding.engine,
            )
            exit_for_earnings = False
        if exit_for_earnings and now.time() >= time(15, 50):
            self._exit(holding)
            return
        daily_frame = self._daily_frames.get(holding.signal)
        if daily_frame is None:
            return
        frame = self._completed(daily_frame, now)
        if len(frame) < 20:
            return
        since = cast(
            DataFrame,
            frame[cast(Any, frame.index) >= holding.entered_at.astimezone(TRADING_ZONE)],
        )
        observed = since if len(since) else frame
        last = float(cast(Any, frame["close"]).iloc[-1])
        holding.highest = max(
            holding.highest,
            float(cast(Any, observed["close"]).max()),
        )
        multiple = 1.5 if holding.engine == "sma" else 2.0
        holding.stop = max(holding.stop, holding.highest - multiple * latest_atr(frame))
        if last < holding.stop or signal_exit(frame):
            self._exit(holding)

    def _manage_orb(self, holding: Holding, now: datetime) -> None:
        price = float(self.get_last_price(holding.asset))
        holding.highest = max(holding.highest, price)
        holding.lowest = min(holding.lowest, price)
        targets = holding.targets
        if targets is None:
            return
        reached = (
            price >= targets[holding.stage]
            if holding.direction == 1
            else price <= targets[holding.stage]
        )
        if reached:
            if holding.stage == 0:
                quantity = holding.original_quantity * 0.5
            elif holding.stage == 1:
                quantity = holding.original_quantity * 0.25
            else:
                self._exit(holding)
                return
            holding.stage += 1
            self._exit(holding, quantity)
            return
        if holding.stage == 0:
            return
        minutes = 5 if holding.engine == "orb" else 10
        timeframe = FIVE_MINUTES if minutes == 5 else TEN_MINUTES
        recent = self._frames([holding.signal], now - timedelta(days=5), timeframe, now).get(
            holding.signal
        )
        if recent is None:
            return
        frame = self._completed(recent, now, minutes)
        frame = cast(DataFrame, cast(Any, frame).between_time("09:30", "15:59"))
        if len(frame) < 15:
            return
        trail = 1.5 * latest_atr(frame)
        candidate = (
            max(holding.entry, holding.highest - trail)
            if holding.direction == 1
            else min(holding.entry, holding.lowest + trail)
        )
        holding.stop = next_stop(holding.direction, holding.stop, candidate)
        self._protect(holding)

    def _enter(
        self,
        engine: StrategyName,
        signal: str,
        asset: str,
        price: float,
        stop: float,
        now: datetime,
        *,
        direction: Direction = 1,
        targets: tuple[float, float, float] | None = None,
        risk_fraction_max: float | None = None,
    ) -> bool:
        if engine not in self._enabled or self._claimed(signal) or direction * (price - stop) <= 0:
            return False
        if direction == -1:
            security = self.broker.api.get_asset(asset)
            if not bool(security.shortable):
                self._event(
                    f"short-{asset}-{now.date()}",
                    "warning",
                    f"Short entry skipped for {asset}: security is not shortable",
                    engine,
                )
                return False
        account = self.broker.api.get_account()
        equity = float(account.portfolio_value)
        positions = cast(list[Any], self.broker.api.get_all_positions())
        gross = sum(abs(float(position.market_value)) for position in positions) + sum(
            pending.notional for pending in self._pending.values()
        )
        if len(positions) + len(self._pending) >= 10 or gross >= equity:
            self._event("capacity", "warning", "Portfolio position capacity reached")
            return False
        risk_fraction = float(self.parameters["risk_per_trade_max"])
        if equity <= 0:
            return False
        if risk_fraction_max is not None:
            risk_fraction = min(risk_fraction, risk_fraction_max)
        quantity = entry_quantity(
            equity,
            price,
            abs(price - stop),
            min(0.10, float(self.parameters["position_fraction_max"])),
            risk_fraction,
            bool(self.parameters["fractional_orders"]),
        )
        notional = float(quantity) * price
        if quantity <= 0 or gross + notional > equity:
            return False
        holding = Holding(
            engine,
            signal,
            asset,
            price,
            stop,
            abs(price - stop),
            price,
            now.astimezone(UTC),
            direction=direction,
            targets=targets,
            lowest=price,
        )
        self._pending[asset] = Pending(holding, now, notional)
        self._claims[signal] = engine
        self._claims[asset] = engine
        order = self.create_order(
            asset,
            quantity,
            "buy" if direction == 1 else "sell",
            time_in_force="day",
            custom_params={
                "client_order_id": self._order_id(engine, "e", signal, holding.risk / price)
            },
        )
        self.submit_order(order)
        return True

    def _protect(self, holding: Holding, quantity: float | None = None) -> None:
        if holding.asset in self._closing:
            return
        amount = self._quantity(holding.asset) if quantity is None else quantity
        price = float(self.get_last_price(holding.asset))
        stop = round(holding.stop, 2)
        if amount <= 0 or stop <= 0:
            return
        if (holding.direction == 1 and stop >= price) or (
            holding.direction == -1 and stop <= price
        ):
            self._exit(holding)
            return
        size = quantity_value(amount, bool(self.parameters["fractional_orders"]))
        if size <= 0:
            return
        if self._stops.get(holding.asset) == (stop, float(size)):
            return
        self._cancel(holding.asset)
        order = self.create_order(
            holding.asset,
            size,
            "sell" if holding.direction == 1 else "buy",
            stop_price=stop,
            time_in_force="day",
            custom_params={
                "client_order_id": self._order_id(
                    holding.engine, "s", holding.signal, holding.risk / holding.entry
                )
            },
        )
        self.submit_order(order)
        self._stops[holding.asset] = (stop, float(size))

    def _exit(self, holding: Holding, quantity: float | None = None) -> None:
        if holding.asset in self._closing:
            return
        current = self._quantity(holding.asset)
        amount = current if quantity is None else min(quantity, current)
        if amount <= 0:
            self._release(holding.asset)
            return
        self._cancel(holding.asset)
        order = self.create_order(
            holding.asset,
            quantity_value(amount, bool(self.parameters["fractional_orders"])),
            "sell" if holding.direction == 1 else "buy",
            time_in_force="day",
            custom_params={
                "client_order_id": self._order_id(
                    holding.engine, "x", holding.signal, holding.risk / holding.entry
                )
            },
        )
        self.submit_order(order)
        self._closing.add(holding.asset)

    def _cancel(self, asset: str) -> None:
        orders = [
            order
            for order in cast(list[Any], self.get_orders())
            if order.is_active() and str(order.asset.symbol) == asset
        ]
        self.cancel_open_orders(orders)
        if orders:
            self.sleep(1)
        self._stops.pop(asset, None)

    def _quantity(self, asset: str) -> float:
        position = self.get_position(asset)
        return 0.0 if position is None else abs(float(position.quantity))

    def _claimed(self, symbol: str) -> bool:
        return symbol in self._claims or symbol in self._pending or symbol in self._holdings

    def _release(self, asset: str) -> None:
        pending = self._pending.pop(asset, None)
        holding = self._holdings.pop(asset, None)
        signal = holding.signal if holding is not None else asset
        if pending is not None:
            signal = pending.holding.signal
        self._claims.pop(asset, None)
        self._claims.pop(signal, None)
        self._stops.pop(asset, None)
        self._closing.discard(asset)

    def _order_id(self, engine: StrategyName, kind: str, signal: str, risk: float) -> str:
        scaled = round(risk * 1_000_000)
        return f"mt-{STRATEGY_CODES[engine]}-{kind}-{signal}-{scaled}-{uuid4().hex[:8]}"

    def _order_engine(self, value: str) -> StrategyName | None:
        return find_order_strategy(value)

    def _order_signal(self, value: str) -> str | None:
        parts = value.split("-")
        return parts[3] if len(parts) == 6 and parts[0] == "mt" else None

    def _order_risk(self, value: str) -> float | None:
        parts = value.split("-")
        return int(parts[4]) / 1_000_000 if self._order_engine(value) is not None else None
