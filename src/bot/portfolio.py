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
from bot.strategies.orb_base import (
    ORB_POSITIONS_MAX,
    ORB_PRICE_MIN,
    ORB_RISK_CEILING,
    ORB_TURNOVER_MIN,
    orb_setup,
    relative_volume_ready,
    round_stop,
)
from bot.strategies.shared import (
    TRADING_ZONE,
    Direction,
    does_macd_confirm,
    earnings_blocked,
    earnings_exit_due,
    entry_quantity,
    fractional_allowed,
    latest_atr,
    latest_dollar_volume,
    market_is_rising,
    momentum_entry,
    next_stop,
    normalize_ohlcv,
    quantity_value,
    signal_exit,
    tfb_entry,
)
from bot.strategies.tfb_50 import TFB_POSITIONS_MAX, TFB_RISK_CEILING, tfb_market_ready
from bot.types import STRATEGY_LABELS, EventLevel, StrategyName, active_strategies


FIVE_MINUTES = TimeFrame(5, cast(TimeFrameUnit, TimeFrameUnit.Minute))
TEN_MINUTES = TimeFrame(10, cast(TimeFrameUnit, TimeFrameUnit.Minute))
# IEX carries a small slice of the tape, so bars built from it understate both
# volume and the width of an opening range. SIP is the consolidated tape.
DATA_FEEDS: dict[str, DataFeed] = {"sip": DataFeed.SIP, "iex": DataFeed.IEX}
# Daily bars are completed history, not the session in progress, so SIP serves
# them without the real-time consolidated subscription the breakout scan needs.
# They are read on SIP whatever ALPACA_DATA_FEED says, because the screens and
# the ranking measure traded value off these bars: IEX carries a small slice of
# the tape, so a $20M turnover floor applied to IEX bars is a far higher bar
# than the same figure applied to the consolidated tape. The configured feed
# still governs every intraday read.
DAILY_FEED = DataFeed.SIP
# One request per fifty symbols turns a universe-wide scan into dozens of round
# trips, and the breakout window is minutes long. Alpaca accepts far more.
SYMBOLS_PER_REQUEST = 200
# The screen reads market cap and turnover, so its volume floor is expressed in
# dollars for the same reason the breakout rules are: a share count means
# different things at $3 and at $300.
UNIVERSE_CAP_MIN = 500_000_000.0
UNIVERSE_TURNOVER_MIN = ORB_TURNOVER_MIN
UNIVERSE_CACHE = Path("/tmp/money-tree-universe.json")
PREPARATION_ATTEMPTS_MAX = 2
STOP_COVERAGE_TOLERANCE = 1e-6
# The register closes intraday positions *before* 15:55 ET. The exit is a market
# order, so it is submitted a minute early to leave room for the fill.
ORB_CLOSE_DEADLINE = time(15, 54)
# The engines that read daily candles, as opposed to the breakout pair.
DAILY_ENGINES: frozenset[StrategyName] = frozenset({"sma", "tfb_50"})
# Whether a daily engine's signal exit waits for both of its conditions or acts
# on either. Both daily engines exit on either: TFB-50's register calls the
# close under its average and weak RSI an emergency exit, and an emergency exit
# that waited for the second condition would hold through the first.
DAILY_EXIT_NEEDS_BOTH: dict[StrategyName, bool] = {"sma": False, "tfb_50": False}
# Whether a daily engine closes a position on the session before the company
# reports. Momentum (SMA) does; TFB-50's register no longer carries the rule, so
# it holds through earnings and leaves on its own threshold and exit instead.
DAILY_EXITS_BEFORE_EARNINGS: dict[StrategyName, bool] = {"sma": True, "tfb_50": False}
# Where each breakout engine's three scale-out targets sit, counted in multiples
# of the risk the fill actually took. ORB-10m's register writes them as fractions
# of the opening range measured from the breakout level — half a range, one range,
# two ranges beyond a stop three quarters of the way back into it — which is the
# same 2R, 4R and 8R, but only while the fill lands *on* the level. A breakout
# candle that closes well past it used to fill above targets already counted as
# reached, and the trade scaled itself out of existence within a minute of opening
# without the price ever going near the stop. Counting from the fill puts every
# target ahead of the entry wherever it lands.
ORB_TARGET_MULTIPLES: dict[StrategyName, tuple[float, float, float]] = {
    "orb": (1.5, 2.5, 4.0),
    "orb_momentum": (2.0, 3.0, 5.0),
}
# How far beyond the breakout level, as a fraction of the opening range, the price
# an order would pay may sit before the breakout is left alone. The stop is a
# fixed distance *inside* the range, so every tick past the level risks more for
# the same setup while leaving less of the move to collect. None is no ceiling.
ORB_ENTRY_EXTENSION_MAX: dict[StrategyName, float | None] = {
    "orb": None,
    "orb_momentum": 0.25,
}
# How far back a breakout close may sit and still be worth taking, counted in
# candles ending at the newest completed one. 1 is the candle that has just
# closed; 2 allows the scan one pass to recover a candle whose bars had not been
# published yet. Beyond that the level is gone and the entry would be a chase.
# Stated per engine because the unit is that engine's own candle: two candles is
# ten minutes of a move for ORB-5m and twenty for ORB-10m, so a bound that suits
# one need not suit the other.
ORB_SIGNAL_CANDLES_MAX: dict[StrategyName, int] = {"orb": 2, "orb_momentum": 2}


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
class DailyCandidate:
    """A daily setup that has passed, priced off the last completed session.

    The daily engines read completed candles only, so a name that qualifies at
    the open still qualifies at the close and its levels do not move. Scanning
    is therefore done once and the list re-offered every iteration: what
    changes through the day is whether there is a free slot and the money to
    take it, not whether the setup holds.
    """

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
    # When the candle that carried the signal closed. The confirmation gates read
    # the market as it stood then, which on a signal recovered a candle late is
    # not where it stands now.
    at: Timestamp | None = None


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
        # One daily entry per symbol per session. The daily engines read
        # completed candles, so the candle that fires an exit can still satisfy
        # an entry; without this a name that stopped out in the morning would be
        # bought straight back on the next iteration, and churn all day.
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
            multiples = ORB_TARGET_MULTIPLES.get(holding.engine)
            if multiples is not None:
                holding.targets = cast(
                    tuple[float, float, float],
                    tuple(
                        holding.entry + holding.direction * holding.risk * multiple
                        for multiple in multiples
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
            multiples = ORB_TARGET_MULTIPLES.get(engine)
            targets: tuple[float, float, float] | None = (
                None
                if multiples is None
                else cast(
                    tuple[float, float, float],
                    tuple(entry + direction * risk * value for value in multiples),
                )
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
            if engine in {"orb", "orb_momentum"}:
                self._orb_traded.add((entered_at.astimezone(TRADING_ZONE).date(), asset))
            if engine in DAILY_ENGINES:
                self._daily_traded.add((entered_at.astimezone(TRADING_ZONE).date(), asset))
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
            daily_frames = self._daily_bars(
                symbols,
                datetime.combine(day - timedelta(days=390), time(), TRADING_ZONE),
                day,
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

    def _daily_bars(self, symbols: list[str], start: datetime, day: date) -> dict[str, DataFrame]:
        """Daily bars on SIP, falling back to the configured feed if SIP is barred.

        Every daily screen, ranking and setup is read off these, so losing them
        stops both daily engines and the breakout ranking for the day. An
        account whose subscription does not serve SIP is better off scanning on
        understated IEX volume — with the substitution on the record — than
        not scanning at all.
        """
        try:
            return self._frames(
                symbols,
                start,
                cast(TimeFrame, TimeFrame.Day),
                feed=DAILY_FEED,
            )
        except Exception as error:
            if DATA_FEEDS[settings.alpaca_data_feed] == DAILY_FEED:
                raise
            self._event(
                f"daily-feed-{day}",
                "warning",
                f"Daily bars fell back to the {settings.alpaca_data_feed} feed: SIP "
                f"refused them ({type(error).__name__}). Turnover floors read low on a "
                "partial feed, so fewer names screen in",
            )
            return self._frames(symbols, start, cast(TimeFrame, TimeFrame.Day))

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
                Query("gte", ["intradaymarketcap", UNIVERSE_CAP_MIN]),
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
                and cap >= UNIVERSE_CAP_MIN
                and price >= ORB_PRICE_MIN
                and volume * price >= UNIVERSE_TURNOVER_MIN
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
        """Offer the day's daily-engine candidates, every iteration until close.

        Nothing here reads the session in progress: the market state and both
        setups are cut from completed candles, so they are scanned once and the
        result re-offered. A name that could not be funded at the open — no
        slot, no affordable size, another engine holding it — is offered again
        as the day frees one up, rather than being lost with a single pass.
        """
        market_frame = self._daily_frames.get("^GSPC")
        if market_frame is None:
            return
        market = self._completed(market_frame, now)
        if not market_is_rising(market):
            self._event("market-state", "warning", "SPX is not above its 20-day average")
            self._daily_candidates = {}
            self._daily_scanned_on = now.date()
            return
        if self._daily_scanned_on != now.date():
            self._daily_scanned_on = now.date()
            self._daily_candidates = {
                engine: self._scan_sma(now) if engine == "sma" else self._scan_tfb(now)
                for engine in self._selected
                if engine in self._enabled and engine in DAILY_ENGINES
            }
        for engine in self._selected:
            if engine == "sma":
                self._run_sma(now)
            if engine == "tfb_50":
                self._run_tfb(now)

    def _ranked(self, now: datetime) -> list[tuple[str, DataFrame]]:
        """Eligible symbols and their completed frames, busiest session first.

        More symbols pass a daily setup on a good morning than there is room to
        hold, and the position cap decides the rest. Walking them in symbol
        order hands the slots to whatever sorts first; walking them by the value
        traded in the last completed session spends them where the money is.
        """
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
            if not momentum_entry(frame):
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
            candidates.append(DailyCandidate(symbol, last, last - 1.5 * latest_atr(frame)))
        return candidates

    def _run_sma(self, now: datetime) -> None:
        for candidate in self._daily_candidates.get("sma", []):
            if self._daily_entered(now.date(), candidate.symbol):
                continue
            self._enter(
                "sma",
                candidate.symbol,
                candidate.symbol,
                candidate.price,
                candidate.stop,
                now,
                caps_risk_per_trade=False,
            )

    def _scan_tfb(self, now: datetime) -> list[DailyCandidate]:
        """This engine screens the universe again on its own price and turnover.

        The shared discovery admits a name on a three-month average share count
        against the current price. TFB-50's register asks for a 20-session
        average of the value actually traded, which is read here from the same
        daily bars the setup is read from.
        """
        candidates: list[DailyCandidate] = []
        for symbol, frame in self._ranked(now):
            if not tfb_market_ready(frame) or not tfb_entry(frame):
                continue
            last = float(cast(Any, frame["close"]).iloc[-1])
            candidates.append(DailyCandidate(symbol, last, last - 2.0 * latest_atr(frame)))
        if not candidates:
            self._event(
                f"tfb-empty-{now.date()}",
                "info",
                "TFB-50 found no candidate: no eligible name passed its screen and setup",
                "tfb_50",
            )
        return candidates

    def _run_tfb(self, now: datetime) -> None:
        for candidate in self._daily_candidates.get("tfb_50", []):
            if self._engine_position_count("tfb_50") >= TFB_POSITIONS_MAX:
                self._event(
                    f"tfb-capacity-{now.date()}",
                    "info",
                    f"TFB-50 entries paused: {TFB_POSITIONS_MAX} positions already open",
                    "tfb_50",
                )
                return
            if self._daily_entered(now.date(), candidate.symbol):
                continue
            self._enter(
                "tfb_50",
                candidate.symbol,
                candidate.symbol,
                candidate.price,
                candidate.stop,
                now,
                risk_fraction_max=TFB_RISK_CEILING,
            )

    def _run_orb(self, now: datetime) -> None:
        self._run_orb_variant("orb", now, 5, 1.3, False, True)

    def _run_orb_momentum(self, now: datetime) -> None:
        self._run_orb_variant("orb_momentum", now, 10, 1.5, False, True)

    def _rank_candidates(self, candidates: list[OrbCandidate], now: datetime) -> list[OrbCandidate]:
        """Breakouts by the value traded in their last completed daily session.

        The relative-volume gate has already asked whether each stock is busy
        against its own history. This asks a different question — which of the
        survivors trades the most money — because the cap they are competing
        for is a money cap.
        """
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

    def _run_orb_variant(
        self,
        engine: StrategyName,
        now: datetime,
        minutes: int,
        volume_multiple: float,
        uses_macd: bool,
        ranks_candidates: bool,
    ) -> None:
        opening_end = time(9, 35) if minutes == 5 else time(9, 40)
        if (
            engine not in self._enabled
            or now.minute % minutes
            or not opening_end <= now.time() <= time(10, 30)
            or not self._eligible_symbols
        ):
            return
        if self._orb_position_count() >= ORB_POSITIONS_MAX:
            self._event(
                f"orb-capacity-{now.date()}",
                "info",
                f"Breakout entries paused: {ORB_POSITIONS_MAX} positions already open",
                engine,
            )
            return
        symbols = self._orb_unscanned(engine, now.date())
        if not symbols:
            return
        if self._orb_data_failed_on == now.date():
            return
        try:
            frames = self._intraday(symbols, now, minutes)
        except Exception as error:
            self._orb_data_unavailable(engine, now.date(), error)
            return
        candidates: list[OrbCandidate] = []
        for symbol in symbols:
            key = (now.date(), engine, symbol)
            frame = frames.get(symbol)
            if frame is None or frame.empty:
                continue
            opening = cast(
                DataFrame,
                cast(Any, frame).between_time("09:30", "09:34" if minutes == 5 else "09:39"),
            )
            after = cast(
                DataFrame,
                frame[cast(Any, cast(DatetimeIndex, frame.index)).time >= opening_end],
            )
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
            # The range is fixed for the day, so a break that fails the setup
            # rules can never pass later: the signal is recorded either way.
            self._orb_scanned.add(key)
            if orb_setup(high, low, close) is None:
                continue
            if len(after) - position > ORB_SIGNAL_CANDLES_MAX[engine]:
                continue
            candidates.append(
                OrbCandidate(
                    symbol, direction, high, low, close, cast(Timestamp, after.index[position])
                )
            )
        if not candidates:
            return
        if ranks_candidates:
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
            self._orb_data_unavailable(engine, now.date(), error)
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
            price = self._orb_price(candidate)
            limit = ORB_ENTRY_EXTENSION_MAX.get(engine)
            if limit is not None and self._too_extended(candidate, price, span, limit):
                self._event(
                    f"extended-{candidate.symbol}-{now.date()}",
                    "warning",
                    f"{candidate.symbol} entry skipped: price is more than "
                    f"{limit:g} of the opening range beyond the breakout level",
                    engine,
                )
                continue
            self._enter(
                engine,
                candidate.symbol,
                candidate.symbol,
                price,
                stop,
                now,
                direction=candidate.direction,
                risk_fraction_max=ORB_RISK_CEILING if engine == "orb" else None,
            )

    def _orb_data_unavailable(self, engine: StrategyName, day: date, error: Exception) -> None:
        """Stand the breakout scan down for the day rather than take the run with it.

        The scan is the only part of an iteration that reads bars for the session
        in progress, and an unreadable feed is not a reason to stop managing
        positions that are already open. The feed is named because the usual
        cause is a data subscription that does not serve the configured one in
        real time, which is fixed by changing ALPACA_DATA_FEED, not the code.
        """
        self._orb_data_failed_on = day
        detail = f"{type(error).__name__}: {error}"
        self._event(
            f"orb-data-{day}",
            "error",
            f"Breakout scan stood down for the day: no intraday bars from the "
            f"{settings.alpaca_data_feed} feed ({detail[:200]})",
            engine,
        )

    def _daily_entered(self, day: date, symbol: str) -> bool:
        """Whether a daily candidate is off the table for the rest of the session."""
        return self._claimed(symbol) or (day, symbol) in self._daily_traded

    def _engine_position_count(self, engine: StrategyName) -> int:
        """Positions one engine holds or has ordered, for a cap of its own."""
        held = sum(1 for holding in self._holdings.values() if holding.engine == engine)
        ordered = sum(
            1
            for asset, pending in self._pending.items()
            if pending.holding.engine == engine and asset not in self._holdings
        )
        return held + ordered

    def _orb_position_count(self) -> int:
        """Breakout positions held or ordered, across both breakout engines.

        Every breakout is the same bet on the same half hour, so the two engines
        share one allowance rather than each taking their own.
        """
        engines = {"orb", "orb_momentum"}
        held = sum(1 for holding in self._holdings.values() if holding.engine in engines)
        ordered = sum(
            1
            for asset, pending in self._pending.items()
            if pending.holding.engine in engines and asset not in self._holdings
        )
        return held + ordered

    def _orb_unscanned(self, engine: StrategyName, day: date) -> list[str]:
        """Symbols still worth pulling bars for, filtered before the fetch.

        The scan runs inside a window minutes wide, so pulling bars for names
        already scanned, traded or held is latency spent on an answer that
        cannot change.
        """
        return [
            symbol
            for symbol in self._eligible_symbols
            if (day, engine, symbol) not in self._orb_scanned
            and (day, symbol) not in self._orb_traded
            and not self._claimed(symbol)
        ]

    def _too_extended(
        self, candidate: OrbCandidate, price: float, span: float, limit: float
    ) -> bool:
        """Whether the price an order would pay sits too far beyond the level.

        The stop sits a fixed distance *inside* the opening range, so a fill
        further past the level is a worse trade twice over: it risks more for the
        same setup, and it has already given away that much of the move. Past the
        ceiling the trade is no longer the breakout the rule named, and no entry
        is better than a stretched one.
        """
        if candidate.direction == 1:
            return price > candidate.high + limit * span
        return price < candidate.low - limit * span

    def _orb_signal(
        self, candles: DataFrame, high: float, low: float
    ) -> tuple[int, Direction, float] | None:
        """The *first* candle since the opening range that closed outside it.

        Reading only the newest candle made the signal depend on which snapshot of
        Alpaca's aggregates happened to have landed. A bar published a few seconds
        after its boundary — routine, since the scan walks the whole universe in
        fifty-symbol pages before the clock is read again — was simply missed, and
        the breakout was then read off the *following* candle. The entry that came
        out of that was a candle's worth of momentum above the level it was meant
        to buy, which is what the charts of 28 August show. Walking the session
        outwards from the range finds the same candle whenever the bars arrive.
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

    def _orb_price(self, candidate: OrbCandidate) -> float:
        """What to size the order on: the live quote, or the breakout close.

        The breakout candle's close is where the signal was read, not what the
        order will pay, and on a signal recovered a candle late it is a whole
        candle stale. Sizing on the live quote also lets _enter turn away a
        breakout the market has already dragged back through its own stop.
        """
        try:
            price = float(self.get_last_price(candidate.symbol))
        except Exception:
            return candidate.close
        return price if isfinite(price) and price > 0 else candidate.close

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
            if now.time() >= ORB_CLOSE_DEADLINE and holding.engine in {"orb", "orb_momentum"}:
                self._exit(holding)
                continue
            if holding.engine in {"sma", "tfb_50"}:
                self._manage_daily(holding, now)
            else:
                self._manage_orb(holding, now)

    def _manage_daily(self, holding: Holding, now: datetime) -> None:
        exit_for_earnings = False
        if DAILY_EXITS_BEFORE_EARNINGS[holding.engine]:
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
        last = float(cast(Any, frame["close"]).iloc[-1])
        # The stop trails the highest close *since entry*. On the entry day there
        # is no such close yet, and `highest` stays at the fill price: falling
        # back to the whole frame here would anchor the stop to a high set months
        # before the trade and stop it out on its first session.
        if len(since):
            holding.highest = max(holding.highest, float(cast(Any, since["close"]).max()))
        multiple = 1.5 if holding.engine == "sma" else 2.0
        holding.stop = max(holding.stop, holding.highest - multiple * latest_atr(frame))
        if last < holding.stop or signal_exit(frame, DAILY_EXIT_NEEDS_BOTH[holding.engine]):
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
        try:
            recent = self._frames([holding.signal], now - timedelta(days=5), timeframe, now).get(
                holding.signal
            )
        except Exception as error:
            # The stop already resting at the broker still protects the position,
            # so a failed read costs an update, not the trade.
            self._event(
                f"trail-{holding.asset}-{now.date()}",
                "warning",
                f"{holding.asset} trailing stop not updated: {type(error).__name__}",
                holding.engine,
            )
            return
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
        risk_fraction_max: float | None = None,
        caps_risk_per_trade: bool = True,
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
            self._event(
                f"capacity-{asset}-{now.date()}",
                "warning",
                f"{asset} entry skipped: portfolio position capacity reached",
                engine,
            )
            return False
        risk_fraction: float | None = float(self.parameters["risk_per_trade_max"])
        if equity <= 0:
            return False
        if risk_fraction_max is not None:
            risk_fraction = risk_fraction_max
        if not caps_risk_per_trade:
            risk_fraction = None
        quantity = entry_quantity(
            equity,
            price,
            abs(price - stop),
            min(0.10, float(self.parameters["position_fraction_max"])),
            risk_fraction,
            fractional_allowed(direction, bool(self.parameters["fractional_orders"])),
        )
        notional = float(quantity) * price
        if quantity <= 0 or gross + notional > equity:
            self._event(
                f"sizing-{asset}-{now.date()}",
                "warning",
                f"{asset} entry skipped: no affordable position size",
                engine,
            )
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
        if engine in {"orb", "orb_momentum"}:
            self._orb_traded.add((now.date(), asset))
        if engine in DAILY_ENGINES:
            self._daily_traded.add((now.date(), asset))
        return True

    def _protect(self, holding: Holding, quantity: float | None = None) -> None:
        if holding.asset in self._closing:
            return
        amount = self._quantity(holding.asset) if quantity is None else quantity
        price = float(self.get_last_price(holding.asset))
        stop = round_stop(holding.direction, holding.stop)
        if amount <= 0 or stop <= 0:
            # A fill can arrive before the position is readable. _resync_stops
            # retries every iteration, but a position with no resting stop is
            # worth saying out loud rather than leaving to the next pass.
            self._event(
                f"unprotected-{holding.asset}-{holding.entered_at.date()}",
                "warning",
                f"{holding.asset} has no resting stop yet: position not readable",
                holding.engine,
            )
            return
        if (holding.direction == 1 and stop >= price) or (
            holding.direction == -1 and stop <= price
        ):
            self._event(
                f"through-stop-{holding.asset}-{holding.entered_at.date()}",
                "warning",
                f"{holding.asset} is already through its stop at {price:.2f}: closing at market",
                holding.engine,
            )
            self._exit(holding)
            return
        size = quantity_value(
            amount,
            fractional_allowed(holding.direction, bool(self.parameters["fractional_orders"])),
        )
        if size <= 0:
            return
        if self._stops.get(holding.asset) == (stop, float(size)):
            return
        self._cancel(holding.asset, "s")
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
        size = quantity_value(
            amount,
            fractional_allowed(holding.direction, bool(self.parameters["fractional_orders"])),
        )
        if size <= 0:
            # A scale-out worth less than a whole share of a short rounds away.
            # Skipping it leaves the position covered by its resting stop; the
            # next target or the closing deadline takes what is left. Cancelling
            # first and then not replacing the stop would strip that protection.
            return
        self._cancel(holding.asset)
        order = self.create_order(
            holding.asset,
            size,
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

    def _cancel(self, asset: str, kind: str | None = None) -> None:
        def matches(order: Any) -> bool:
            if not order.is_active() or str(order.asset.symbol) != asset:
                return False
            identifier = str(getattr(order, "client_order_id", "") or "")
            return kind is None or self._order_kind(identifier) == kind

        orders = [order for order in cast(list[Any], self.get_orders()) if matches(order)]
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

    def _order_kind(self, value: str) -> str | None:
        parts = value.split("-")
        return parts[2] if len(parts) == 6 and parts[0] == "mt" else None

    def _order_signal(self, value: str) -> str | None:
        parts = value.split("-")
        return parts[3] if len(parts) == 6 and parts[0] == "mt" else None

    def _order_risk(self, value: str) -> float | None:
        parts = value.split("-")
        return int(parts[4]) / 1_000_000 if self._order_engine(value) is not None else None
