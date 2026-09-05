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

from .config import settings
from .export import log_event
from .order_tag import find_order_tag, order_tag
from .strategies.base import StrategyBase
from .strategies.daily_base import (
    DAILY_EARNINGS_EXIT_LEAD_MINUTES,
    DAILY_EXITS_BEFORE_EARNINGS,
    DAILY_HISTORY_SESSIONS,
    DAILY_RISK_MAX,
    DAILY_STOP_ATR_MULTIPLES,
    DAILY_STRATEGIES,
)
from .strategies.orb_base import (
    ORB_CLOSE_LEAD_MINUTES,
    ORB_ENTRY_EXTENSION_MAX,
    ORB_OPENING_MINUTES,
    ORB_POSITIONS_MAX,
    ORB_PRICE_USD_MIN,
    ORB_RISK_MAX,
    ORB_SCAN_MINUTES,
    ORB_SIGNAL_CANDLES_MAX,
    ORB_STRATEGIES,
    ORB_TARGET_MULTIPLES,
    ORB_TRAIL_ATR_MULTIPLE,
    ORB_TRAIL_BARS_MIN,
    ORB_TURNOVER_USD_MIN,
    ORB_VOLUME_MULTIPLES,
    is_orb_setup_ready,
    is_relative_volume_ready,
    round_stop,
)
from .strategies.shared import (
    TRADING_ZONE,
    Direction,
    does_momentum_enter,
    does_signal_exit,
    does_tfb_enter,
    entry_quantity,
    is_earnings_blocked,
    is_earnings_exit_due,
    is_fractional_allowed,
    latest_atr,
    latest_dollar_volume,
    market_is_rising,
    next_stop,
    normalize_ohlcv,
    quantity_value,
    regular_session,
    session_bounds,
)
from .strategies.tfb_50 import TFB_POSITIONS_MAX, is_tfb_market_ready
from .types import (
    POSITION_FRACTION_CAP_MAX,
    POSITIONS_MAX,
    STRATEGY_LABELS,
    EventLevel,
    StrategyName,
    active_strategies,
)


yfinance = cast(Any, import_module("yfinance"))


@dataclass(slots=True)
class Holding:
    strategy: StrategyName
    symbol: str
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
class DailyCandidate:
    symbol: str
    price: float
    stop: float


@dataclass(frozen=True, slots=True)
class OrbCandidate:
    symbol: str
    direction: Direction
    high: float
    low: float
    close: float
    at: Timestamp | None = None


class LoadUniverseError(Exception):
    pass


FIVE_MINUTES = TimeFrame(5, cast(TimeFrameUnit, TimeFrameUnit.Minute))
TEN_MINUTES = TimeFrame(10, cast(TimeFrameUnit, TimeFrameUnit.Minute))
DATA_FEEDS: dict[str, DataFeed] = {
    "sip": DataFeed.SIP,
    "delayed_sip": DataFeed.DELAYED_SIP,
    "iex": DataFeed.IEX,
}
DAILY_FEED = DataFeed.SIP
SYMBOLS_PER_REQUEST = 200
ORDERS_PER_REQUEST = 500
UNIVERSE_CAP_USD_MIN = 500_000_000.0
UNIVERSE_TURNOVER_USD_MIN = ORB_TURNOVER_USD_MIN
UNIVERSE_HISTORY_DAYS = 390
UNIVERSE_CACHE = Path("/tmp/money-tree-universe.json")
PREPARATION_ATTEMPTS_MAX = 2
STOP_COVERAGE_DRIFT_MAX = 1e-6
PENDING_TTL_MINUTES = 5
STRATEGY_RISK_MAX: dict[StrategyName, float | None] = {"orb": ORB_RISK_MAX, **DAILY_RISK_MAX}


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
        self._daily_traded: set[tuple[date, str]] = set()
        self._orb_scanned: set[tuple[date, StrategyName, str]] = set()
        self._day: date | None = None
        self._baseline_equity = 0.0
        self._locked_on: date | None = None
        self._daily_frames: dict[str, DataFrame] = {}
        self._eligible_symbols: list[str] = []
        self._prepared_on: date | None = None
        self._preparation_attempts = 0
        self._preparation_attempts_on: date | None = None
        self._daily_candidates: dict[StrategyName, list[DailyCandidate]] = {}
        self._daily_scanned_on: date | None = None
        self._orb_data_failed_on: date | None = None
        self._intraday_bucket: datetime | None = None
        self._restored = False
        self._data = StockHistoricalDataClient(
            settings.alpaca_api_key.get_secret_value(),
            settings.alpaca_api_secret.get_secret_value(),
        )

    def before_market_opens(self) -> None:
        self._restore()
        self._prepare(self.get_datetime().astimezone(TRADING_ZONE).date())

    def on_trading_iteration(self) -> None:
        now = self.get_datetime().astimezone(TRADING_ZONE)
        bounds = session_bounds(now.date())
        if bounds is None:
            return
        opens, closes = bounds
        self._restore()
        self._begin_day(now.date())
        self._reconcile(now)
        if self._is_daily_loss_reached(now.date()):
            return
        self._prepare(now.date())
        self._manage(now, closes)
        self._run_daily(now)
        bucket = now.replace(second=0, microsecond=0)
        if now.minute % 5 == 0 and bucket != self._intraday_bucket:
            self._intraday_bucket = bucket
            for strategy in ORB_OPENING_MINUTES:
                self._run_orb(strategy, now, opens)

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
            holding.original_quantity = max(self._quantity(symbol), abs(float(quantity)))
            holding.targets = self._targets(holding)
            self._holdings[symbol] = holding
            if holding.strategy in ORB_STRATEGIES:
                self._protect(holding)
            return
        self._closing.discard(symbol)
        remaining = abs(float(getattr(position, "quantity", 0.0)))
        if remaining <= 0:
            self._release(symbol)
        elif symbol in self._holdings:
            holding = self._holdings[symbol]
            if holding.stage == 0:
                holding.original_quantity = max(holding.original_quantity, remaining)
            self._protect(holding, remaining)

    def _entry_price(self, order: Any, price: float) -> float:
        average = getattr(order, "avg_fill_price", None)
        value = 0.0 if average is None else float(average)
        return value if isfinite(value) and value > 0 else float(price)

    def _targets(self, holding: Holding) -> tuple[float, float, float] | None:
        multiples = ORB_TARGET_MULTIPLES.get(holding.strategy)
        if multiples is None:
            return None
        return cast(
            tuple[float, float, float],
            tuple(
                holding.entry + holding.direction * holding.risk * multiple
                for multiple in multiples
            ),
        )

    def _record_event(
        self,
        key: str,
        level: EventLevel,
        message: str,
        strategy: StrategyName | None = None,
    ) -> None:
        if key in self._events:
            return
        self._events.add(key)
        label = None if strategy is None else STRATEGY_LABELS[strategy]
        if self.exporter is None:
            # A backtest has no dashboard to report to. The log still wants it.
            log_event(key, level, message, label)
            return
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

    def _is_daily_loss_reached(self, day: date) -> bool:
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
        self._record_event("day.loss_reached", "warning", "Daily loss limit reached")
        return True

    def _restore(self) -> None:
        if self._restored:
            return
        for strategy in sorted(self._exit_only):
            self._record_event(
                f"strategy.paused.{strategy}",
                "warning",
                f"{strategy} is paused: existing positions only, no new entries",
                strategy,
            )
        self._record_event(
            "feed.announced",
            "info",
            f"Intraday strategies use Alpaca {settings.alpaca_data_feed} market data",
        )
        positions = cast(list[Any], self.broker.api.get_all_positions())
        self._restored = True
        symbols = sorted({str(position.symbol) for position in positions})
        if not symbols:
            return
        request = GetOrdersRequest(
            status=QueryOrderStatus.ALL,
            symbols=symbols,
            limit=ORDERS_PER_REQUEST,
            direction=Sort.DESC,
        )
        orders = cast(list[Any], self.broker.api.get_orders(filter=request))
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
            strategy = held[0][1].strategy
            entry_order, entry_tag = next(
                (
                    (order, tag)
                    for order, tag in held
                    if tag.kind == "e" and tag.strategy == strategy
                ),
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
                entry,
                entry - direction * risk,
                risk,
                entry,
                entered_at,
                direction=direction,
                original_quantity=original,
                lowest=entry,
            )
            holding.targets = self._targets(holding)
            remaining_fraction = abs(quantity) / original
            if strategy in ORB_STRATEGIES and remaining_fraction <= 0.5:
                holding.stage = 1 if remaining_fraction > 0.25 else 2
            self._holdings[symbol] = holding
            self._claims[symbol] = strategy
            traded_on = entered_at.astimezone(TRADING_ZONE).date()
            if strategy in ORB_STRATEGIES:
                self._orb_traded.add((traded_on, symbol))
            if strategy in DAILY_STRATEGIES:
                self._daily_traded.add((traded_on, symbol))
            if strategy not in self._enabled:
                self._exit_only.add(strategy)
                self._record_event(
                    f"strategy.exits_only.{strategy}",
                    "warning",
                    f"{strategy} is managing existing positions only",
                    strategy,
                )

    def _reconcile(self, now: datetime) -> None:
        positions = {str(value.symbol): value for value in self.broker.api.get_all_positions()}
        for symbol in list(self._holdings):
            if symbol not in positions:
                self._release(symbol)
        active = {
            str(order.asset.symbol)
            for order in cast(list[Any], self.get_orders())
            if order.is_active()
        }
        for symbol, pending in list(self._pending.items()):
            expired = now - pending.submitted_at > timedelta(minutes=PENDING_TTL_MINUTES)
            if symbol not in positions and symbol not in active and expired:
                self._release(symbol)
        for symbol in set(self._stops).difference(active):
            self._stops.pop(symbol, None)
        self._closing.intersection_update(active)
        self._resync_stops(positions)

    def _resync_stops(self, positions: dict[str, Any]) -> None:
        for symbol, holding in self._holdings.items():
            if holding.strategy not in ORB_STRATEGIES or symbol in self._closing:
                continue
            position = positions.get(symbol)
            if position is None:
                continue
            quantity = abs(float(position.qty))
            if quantity <= 0:
                continue
            if holding.stage == 0:
                holding.original_quantity = max(holding.original_quantity, quantity)
            resting = self._stops.get(symbol)
            if resting is None or resting[1] < quantity - STOP_COVERAGE_DRIFT_MAX:
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
            held = set(self._holdings)
            symbols = sorted(set(eligible).union({"SPY", "QQQ"}, held))
            daily_frames = self._frames(
                symbols,
                datetime.combine(day - timedelta(days=UNIVERSE_HISTORY_DAYS), time(), TRADING_ZONE),
                cast(TimeFrame, TimeFrame.Day),
                feed=DAILY_FEED,
            )
            spx = self._spx(day)
            if spx is not None:
                daily_frames["^GSPC"] = spx
        except Exception as error:
            self._daily_frames = {}
            self._eligible_symbols = []
            self._record_event(
                "universe.unavailable", "error", f"Stock universe unavailable: {error}"
            )
            return
        self._daily_frames = daily_frames
        self._eligible_symbols = eligible
        self._prepared_on = day

    def _spx(self, day: date) -> DataFrame | None:
        try:
            frame = yfinance.Ticker("^GSPC").history(
                start=day - timedelta(days=UNIVERSE_HISTORY_DAYS),
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
            self._record_event(
                "market.unavailable",
                "error",
                f"SPX market state unavailable: {type(error).__name__}",
            )
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
        Query = yfinance.EquityQuery
        query = Query(
            "and",
            [
                Query("eq", ["region", "us"]),
                Query("gte", ["intradaymarketcap", UNIVERSE_CAP_USD_MIN]),
            ],
        )
        quotes: list[dict[str, Any]] = []
        offset = 0
        while True:
            page = yfinance.screen(
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
                float(value.get("regularMarketPrice") or 0),
            )
            for value in quotes
            if value.get("quoteType") == "EQUITY"
        ]
        return sorted(
            {
                symbol
                for symbol, cap, volume, price in rows
                if symbol in assets
                and cap >= UNIVERSE_CAP_USD_MIN
                and price >= ORB_PRICE_USD_MIN
                and volume * price >= UNIVERSE_TURNOVER_USD_MIN
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
        self,
        symbols: list[str],
        start: datetime,
        timeframe: TimeFrame,
        end: datetime | None = None,
        feed: DataFeed | None = None,
    ) -> dict[str, DataFrame]:
        frames: dict[str, DataFrame] = {}
        for offset in range(0, len(symbols), SYMBOLS_PER_REQUEST):
            request = StockBarsRequest(
                symbol_or_symbols=symbols[offset : offset + SYMBOLS_PER_REQUEST],
                start=start.astimezone(UTC),
                end=None if end is None else end.astimezone(UTC),
                timeframe=timeframe,
                adjustment=Adjustment.ALL,
                feed=DATA_FEEDS[settings.alpaca_data_feed] if feed is None else feed,
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
            self._record_event("market.stalled", "warning", "SPX is not above its 20-day average")
            self._daily_candidates = {}
            self._daily_scanned_on = now.date()
            return
        if self._daily_scanned_on != now.date():
            self._daily_scanned_on = now.date()
            self._daily_candidates = {
                strategy: self._scan_sma(now) if strategy == "sma" else self._scan_tfb(now)
                for strategy in self._selected
                if strategy in self._enabled and strategy in DAILY_STRATEGIES
            }
        for strategy in self._selected:
            if strategy == "sma":
                self._run_sma(now)
            if strategy == "tfb_50":
                self._run_tfb(now)

    def _ranked(self, now: datetime) -> list[tuple[str, DataFrame]]:
        ranked: list[tuple[float, str, DataFrame]] = []
        for symbol in self._eligible_symbols:
            daily_frame = self._daily_frames.get(symbol)
            if daily_frame is None:
                continue
            frame = self._completed(daily_frame, now)
            ranked.append((latest_dollar_volume(frame), symbol, frame))
        ranked.sort(key=lambda row: (-row[0], row[1]))
        return [(symbol, frame) for _, symbol, frame in ranked]

    def _scan_sma(self, now: datetime) -> list[DailyCandidate]:
        candidates: list[DailyCandidate] = []
        for symbol, frame in self._ranked(now):
            if not does_momentum_enter(frame):
                continue
            try:
                blocked = is_earnings_blocked(symbol, now.date())
            except Exception as error:
                self._record_event(
                    f"earnings.unavailable.{symbol}",
                    "error",
                    f"Earnings calendar unavailable for {symbol}: {type(error).__name__}",
                    "sma",
                )
                continue
            if blocked:
                continue
            last = float(cast(Any, frame["close"]).iloc[-1])
            stop = last - DAILY_STOP_ATR_MULTIPLES["sma"] * latest_atr(frame)
            candidates.append(DailyCandidate(symbol, last, stop))
        return candidates

    def _run_sma(self, now: datetime) -> None:
        for candidate in self._daily_candidates.get("sma", []):
            if self._is_daily_entered(now.date(), candidate.symbol):
                continue
            self._enter("sma", candidate.symbol, candidate.price, candidate.stop, now)

    def _scan_tfb(self, now: datetime) -> list[DailyCandidate]:
        candidates: list[DailyCandidate] = []
        for symbol, frame in self._ranked(now):
            if not is_tfb_market_ready(frame) or not does_tfb_enter(frame):
                continue
            last = float(cast(Any, frame["close"]).iloc[-1])
            stop = last - DAILY_STOP_ATR_MULTIPLES["tfb_50"] * latest_atr(frame)
            candidates.append(DailyCandidate(symbol, last, stop))
        if not candidates:
            self._record_event(
                f"tfb.emptied.{now.date()}",
                "info",
                "TFB-50 found no candidate: no eligible name passed its screen and setup",
                "tfb_50",
            )
        return candidates

    def _run_tfb(self, now: datetime) -> None:
        for candidate in self._daily_candidates.get("tfb_50", []):
            if self._strategy_position_count("tfb_50") >= TFB_POSITIONS_MAX:
                self._record_event(
                    f"tfb.capped.{now.date()}",
                    "info",
                    f"TFB-50 entries paused: {TFB_POSITIONS_MAX} positions already open",
                    "tfb_50",
                )
                return
            if self._is_daily_entered(now.date(), candidate.symbol):
                continue
            self._enter("tfb_50", candidate.symbol, candidate.price, candidate.stop, now)

    def _rank_candidates(self, candidates: list[OrbCandidate], now: datetime) -> list[OrbCandidate]:
        ranked: list[tuple[float, str, OrbCandidate]] = []
        for candidate in candidates:
            daily_frame = self._daily_frames.get(candidate.symbol)
            traded = (
                0.0
                if daily_frame is None
                else latest_dollar_volume(self._completed(daily_frame, now))
            )
            ranked.append((traded, candidate.symbol, candidate))
        ranked.sort(key=lambda row: (-row[0], row[1]))
        return [candidate for _, _, candidate in ranked]

    def _run_orb(self, strategy: StrategyName, now: datetime, opens: datetime) -> None:
        minutes = ORB_OPENING_MINUTES[strategy]
        opening_end = opens + timedelta(minutes=minutes)
        scan_end = opens + timedelta(minutes=ORB_SCAN_MINUTES)
        if (
            strategy not in self._enabled
            or now.minute % minutes
            or not opening_end <= now <= scan_end
            or not self._eligible_symbols
        ):
            return
        if self._orb_position_count() >= ORB_POSITIONS_MAX:
            self._record_event(
                f"orb.capped.{now.date()}",
                "info",
                f"Breakout entries paused: {ORB_POSITIONS_MAX} positions already open",
                strategy,
            )
            return
        symbols = self._orb_unscanned(strategy, now.date())
        if not symbols or self._orb_data_failed_on == now.date():
            return
        try:
            frames = self._intraday(symbols, now, opens, minutes)
        except Exception as error:
            self._orb_data_unavailable(strategy, now.date(), error)
            return
        candidates = self._orb_candidates(strategy, frames, now, opens, opening_end)
        if not candidates:
            return
        candidates = self._rank_candidates(candidates, now)
        timeframe = FIVE_MINUTES if minutes == 5 else TEN_MINUTES
        try:
            histories = self._frames(
                [candidate.symbol for candidate in candidates],
                now - timedelta(days=45),
                timeframe,
                now,
            )
        except Exception as error:
            self._orb_data_unavailable(strategy, now.date(), error)
            return
        for candidate in candidates:
            if self._orb_position_count() >= ORB_POSITIONS_MAX:
                return
            frame = histories.get(candidate.symbol)
            if frame is None:
                continue
            completed = self._completed(frame, now, minutes)
            if candidate.at is not None:
                completed = cast(DataFrame, completed[cast(Any, completed.index) <= candidate.at])
            if not self._orb_confirm(completed, now, ORB_VOLUME_MULTIPLES[strategy]):
                continue
            span = candidate.high - candidate.low
            stop = candidate.low + span * (0.75 if candidate.direction == 1 else 0.25)
            price = self._orb_price(candidate)
            limit = ORB_ENTRY_EXTENSION_MAX[strategy]
            if limit is not None and self._is_too_extended(candidate, price, span, limit):
                self._record_event(
                    f"entry.overextended.{candidate.symbol}.{now.date()}",
                    "warning",
                    f"{candidate.symbol} entry skipped: price is more than "
                    f"{limit:g} of the opening range beyond the breakout level",
                    strategy,
                )
                continue
            self._enter(strategy, candidate.symbol, price, stop, now, direction=candidate.direction)

    def _orb_candidates(
        self,
        strategy: StrategyName,
        frames: dict[str, DataFrame],
        now: datetime,
        opens: datetime,
        opening_end: datetime,
    ) -> list[OrbCandidate]:
        candidates: list[OrbCandidate] = []
        for symbol, frame in frames.items():
            if frame.empty:
                continue
            index = cast(Any, cast(DatetimeIndex, frame.index))
            opening = cast(DataFrame, frame[(index >= opens) & (index < opening_end)])
            after = cast(DataFrame, frame[index >= opening_end])
            if opening.empty or after.empty:
                continue
            high = float(cast(Any, opening["high"]).max())
            low = float(cast(Any, opening["low"]).min())
            if not all(isfinite(value) for value in (high, low)):
                continue
            signal = self._orb_signal(after, high, low)
            if signal is None:
                continue
            position, direction, close = signal
            self._orb_scanned.add((now.date(), strategy, symbol))
            if not is_orb_setup_ready(high, low, close):
                continue
            if len(after) - position > ORB_SIGNAL_CANDLES_MAX:
                continue
            candidates.append(
                OrbCandidate(
                    symbol, direction, high, low, close, cast(Timestamp, after.index[position])
                )
            )
        return candidates

    def _orb_data_unavailable(self, strategy: StrategyName, day: date, error: Exception) -> None:
        self._orb_data_failed_on = day
        detail = f"{type(error).__name__}: {error}"
        self._record_event(
            f"orb.unavailable.{day}",
            "error",
            f"Breakout scan stood down for the day: no intraday bars from the "
            f"{settings.alpaca_data_feed} feed ({detail[:200]})",
            strategy,
        )

    def _is_daily_entered(self, day: date, symbol: str) -> bool:
        return self._is_claimed(symbol) or (day, symbol) in self._daily_traded

    def _strategy_position_count(self, strategy: StrategyName) -> int:
        return self._position_count(frozenset({strategy}))

    def _orb_position_count(self) -> int:
        return self._position_count(ORB_STRATEGIES)

    def _position_count(self, strategies: frozenset[StrategyName]) -> int:
        held = sum(1 for holding in self._holdings.values() if holding.strategy in strategies)
        ordered = sum(
            1
            for symbol, pending in self._pending.items()
            if pending.holding.strategy in strategies and symbol not in self._holdings
        )
        return held + ordered

    def _orb_unscanned(self, strategy: StrategyName, day: date) -> list[str]:
        return [
            symbol
            for symbol in self._eligible_symbols
            if (day, strategy, symbol) not in self._orb_scanned
            and (day, symbol) not in self._orb_traded
            and not self._is_claimed(symbol)
        ]

    def _is_too_extended(
        self, candidate: OrbCandidate, price: float, span: float, limit: float
    ) -> bool:
        if candidate.direction == 1:
            return price > candidate.high + limit * span
        return price < candidate.low - limit * span

    def _orb_signal(
        self, candles: DataFrame, high: float, low: float
    ) -> tuple[int, Direction, float] | None:
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

    def _orb_price(self, candidate: OrbCandidate) -> float:
        price = float(self.get_last_price(candidate.symbol))
        return price if isfinite(price) and price > 0 else candidate.close

    def _intraday(
        self, symbols: list[str], now: datetime, opens: datetime, minutes: int
    ) -> dict[str, DataFrame]:
        timeframe = FIVE_MINUTES if minutes == 5 else TEN_MINUTES
        return {
            symbol: self._completed(frame, now, minutes)
            for symbol, frame in self._frames(symbols, opens, timeframe, now).items()
        }

    def _orb_confirm(self, frame: DataFrame, now: datetime, volume_multiple: float) -> bool:
        if frame.empty:
            return False
        return is_relative_volume_ready(
            frame,
            now.date(),
            cast(Timestamp, frame.index[-1]).time(),
            volume_multiple,
        )

    def _manage(self, now: datetime, closes: datetime) -> None:
        orb_deadline = closes - timedelta(minutes=ORB_CLOSE_LEAD_MINUTES)
        for holding in list(self._holdings.values()):
            if now >= orb_deadline and holding.strategy in ORB_STRATEGIES:
                self._exit(holding)
                continue
            if holding.strategy in DAILY_STRATEGIES:
                self._manage_daily(holding, now, closes)
            else:
                self._manage_orb(holding, now)

    def _manage_daily(self, holding: Holding, now: datetime, closes: datetime) -> None:
        exit_for_earnings = False
        if DAILY_EXITS_BEFORE_EARNINGS[holding.strategy]:
            try:
                exit_for_earnings = is_earnings_exit_due(holding.symbol, now.date())
            except Exception as error:
                self._record_event(
                    f"earnings.unavailable.{holding.symbol}",
                    "error",
                    f"Earnings calendar unavailable for {holding.symbol}: {type(error).__name__}",
                    holding.strategy,
                )
                exit_for_earnings = False
        earnings_deadline = closes - timedelta(minutes=DAILY_EARNINGS_EXIT_LEAD_MINUTES)
        if exit_for_earnings and now >= earnings_deadline:
            self._exit(holding)
            return
        daily_frame = self._daily_frames.get(holding.symbol)
        if daily_frame is None:
            return
        frame = self._completed(daily_frame, now)
        if len(frame) < DAILY_HISTORY_SESSIONS:
            return
        since = cast(
            DataFrame,
            frame[cast(Any, frame.index) >= holding.entered_at.astimezone(TRADING_ZONE)],
        )
        last = float(cast(Any, frame["close"]).iloc[-1])
        if len(since):
            holding.highest = max(holding.highest, float(cast(Any, since["close"]).max()))
        multiple = DAILY_STOP_ATR_MULTIPLES[holding.strategy]
        holding.stop = max(holding.stop, holding.highest - multiple * latest_atr(frame))
        if last < holding.stop or does_signal_exit(frame):
            self._exit(holding)

    def _manage_orb(self, holding: Holding, now: datetime) -> None:
        price = float(self.get_last_price(holding.symbol))
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
        minutes = ORB_OPENING_MINUTES[holding.strategy]
        timeframe = FIVE_MINUTES if minutes == 5 else TEN_MINUTES
        try:
            recent = self._frames([holding.symbol], now - timedelta(days=5), timeframe, now).get(
                holding.symbol
            )
        except Exception as error:
            self._record_event(
                f"trail.stalled.{holding.symbol}.{now.date()}",
                "warning",
                f"{holding.symbol} trailing stop not updated: {type(error).__name__}",
                holding.strategy,
            )
            return
        if recent is None:
            return
        frame = regular_session(self._completed(recent, now, minutes))
        if len(frame) < ORB_TRAIL_BARS_MIN:
            return
        trail = ORB_TRAIL_ATR_MULTIPLE * latest_atr(frame)
        candidate = (
            max(holding.entry, holding.highest - trail)
            if holding.direction == 1
            else min(holding.entry, holding.lowest + trail)
        )
        holding.stop = next_stop(holding.direction, holding.stop, candidate)
        self._protect(holding)

    def _enter(
        self,
        strategy: StrategyName,
        symbol: str,
        price: float,
        stop: float,
        now: datetime,
        *,
        direction: Direction = 1,
    ) -> bool:
        if (
            strategy not in self._enabled
            or self._is_claimed(symbol)
            or direction * (price - stop) <= 0
        ):
            return False
        if direction == -1 and not bool(self.broker.api.get_asset(symbol).shortable):
            self._record_event(
                f"short.refused.{symbol}.{now.date()}",
                "warning",
                f"Short entry skipped for {symbol}: security is not shortable",
                strategy,
            )
            return False
        account = self.broker.api.get_account()
        equity = float(account.portfolio_value)
        positions = cast(list[Any], self.broker.api.get_all_positions())
        gross = sum(abs(float(position.market_value)) for position in positions) + sum(
            pending.notional for pending in self._pending.values()
        )
        if len(positions) + len(self._pending) >= POSITIONS_MAX or gross >= equity:
            self._record_event(
                f"portfolio.capped.{symbol}.{now.date()}",
                "warning",
                f"{symbol} entry skipped: portfolio position capacity reached",
                strategy,
            )
            return False
        if equity <= 0:
            return False
        risk_fraction = STRATEGY_RISK_MAX.get(
            strategy, float(self.parameters["risk_per_trade_max"])
        )
        quantity = entry_quantity(
            equity,
            price,
            abs(price - stop),
            min(POSITION_FRACTION_CAP_MAX, float(self.parameters["position_fraction_max"])),
            risk_fraction,
            is_fractional_allowed(direction, bool(self.parameters["fractional_orders"])),
        )
        notional = float(quantity) * price
        if quantity <= 0 or gross + notional > equity:
            self._record_event(
                f"size.rejected.{symbol}.{now.date()}",
                "warning",
                f"{symbol} entry skipped: no affordable position size",
                strategy,
            )
            return False
        holding = Holding(
            strategy,
            symbol,
            price,
            stop,
            abs(price - stop),
            price,
            now.astimezone(UTC),
            direction=direction,
            lowest=price,
        )
        self._pending[symbol] = Pending(holding, now, notional)
        self._claims[symbol] = strategy
        order = self.create_order(
            symbol,
            quantity,
            "buy" if direction == 1 else "sell",
            time_in_force="day",
            custom_params={
                "client_order_id": order_tag(strategy, "e", symbol, holding.risk / price)
            },
        )
        self.submit_order(order)
        if strategy in ORB_STRATEGIES:
            self._orb_traded.add((now.date(), symbol))
        if strategy in DAILY_STRATEGIES:
            self._daily_traded.add((now.date(), symbol))
        return True

    def _protect(self, holding: Holding, quantity: float | None = None) -> None:
        if holding.symbol in self._closing:
            return
        amount = self._quantity(holding.symbol) if quantity is None else quantity
        price = float(self.get_last_price(holding.symbol))
        stop = round_stop(holding.direction, holding.stop)
        if amount <= 0 or stop <= 0:
            self._record_event(
                f"stop.unplaced.{holding.symbol}.{holding.entered_at.date()}",
                "warning",
                f"{holding.symbol} has no resting stop yet: position not readable",
                holding.strategy,
            )
            return
        if (holding.direction == 1 and stop >= price) or (
            holding.direction == -1 and stop <= price
        ):
            self._record_event(
                f"stop.passed.{holding.symbol}.{holding.entered_at.date()}",
                "warning",
                f"{holding.symbol} is already through its stop at {price:.2f}: closing at market",
                holding.strategy,
            )
            self._exit(holding)
            return
        size = quantity_value(
            amount,
            is_fractional_allowed(holding.direction, bool(self.parameters["fractional_orders"])),
        )
        if size <= 0 or self._stops.get(holding.symbol) == (stop, float(size)):
            return
        self._cancel(holding.symbol, "s")
        order = self.create_order(
            holding.symbol,
            size,
            "sell" if holding.direction == 1 else "buy",
            stop_price=stop,
            time_in_force="day",
            custom_params={
                "client_order_id": order_tag(
                    holding.strategy, "s", holding.symbol, holding.risk / holding.entry
                )
            },
        )
        self.submit_order(order)
        self._stops[holding.symbol] = (stop, float(size))

    def _exit(self, holding: Holding, quantity: float | None = None) -> None:
        if holding.symbol in self._closing:
            return
        current = self._quantity(holding.symbol)
        amount = current if quantity is None else min(quantity, current)
        if amount <= 0:
            self._release(holding.symbol)
            return
        size = quantity_value(
            amount,
            is_fractional_allowed(holding.direction, bool(self.parameters["fractional_orders"])),
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
                    holding.strategy, "x", holding.symbol, holding.risk / holding.entry
                )
            },
        )
        self.submit_order(order)
        self._closing.add(holding.symbol)

    def _cancel(self, symbol: str, kind: str | None = None) -> None:
        def matches(order: Any) -> bool:
            if not order.is_active() or str(order.asset.symbol) != symbol:
                return False
            tag = find_order_tag(str(getattr(order, "client_order_id", "") or ""))
            return kind is None or (tag is not None and tag.kind == kind)

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
