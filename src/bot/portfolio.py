import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from importlib import import_module
from pathlib import Path
from typing import Any, cast
from uuid import uuid4
from zoneinfo import ZoneInfo

from alpaca.common.enums import Sort
from alpaca.data.enums import Adjustment, DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.trading.enums import QueryOrderStatus
from alpaca.trading.requests import GetOrdersRequest
from lumibot.constants import LUMIBOT_DEFAULT_TIMEZONE
from pandas import DataFrame

from bot.config import settings
from bot.strategies.base import StrategyBase
from bot.strategies.orb_base import relative_volume_ready
from bot.strategies.shared import (
    Direction,
    does_macd_confirm,
    earnings_blocked,
    earnings_exit_due,
    entry_quantity,
    latest_atr,
    market_is_rising,
    momentum_entry,
    next_stop,
    quantity_value,
    signal_exit,
    tfb_entry,
)
from bot.types import StrategyName


TRADING_ZONE = ZoneInfo(LUMIBOT_DEFAULT_TIMEZONE)
FIVE_MINUTES = TimeFrame(5, cast(TimeFrameUnit, TimeFrameUnit.Minute))
TEN_MINUTES = TimeFrame(10, cast(TimeFrameUnit, TimeFrameUnit.Minute))
UNIVERSE_CACHE = Path("/tmp/money-tree-universe.json")
ENGINE_CODES: dict[StrategyName, str] = {
    "noop": "n",
    "orb": "o",
    "sma": "s",
    "tfb_50": "t",
    "orb_momentum": "m",
}
CODES_ENGINE: dict[str, StrategyName] = {code: name for name, code in ENGINE_CODES.items()}


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


def _clock(frame: Any) -> Any:
    values = frame.copy()
    if values.empty:
        return values
    index = values.index
    if index.tz is None:
        index = index.tz_localize(UTC)
    values.index = index.tz_convert(TRADING_ZONE)
    return values.sort_index()


class Strategy(StrategyBase):
    def initialize(self) -> None:
        self.sleeptime = "1M"
        self.minutes_before_opening = 30
        selected = cast(list[StrategyName], self.parameters["strategies"])
        self._selected = selected
        self._enabled = set(selected)
        self._exit_only: set[StrategyName] = set()
        self._holdings: dict[str, Holding] = {}
        self._pending: dict[str, Pending] = {}
        self._claims: dict[str, StrategyName | None] = {}
        self._stops: dict[str, float] = {}
        self._closing: set[str] = set()
        self._events: set[str] = set()
        self._orb_traded: set[tuple[date, str]] = set()
        self._orb_scanned: set[tuple[date, StrategyName, str]] = set()
        self._day: date | None = None
        self._baseline_equity = 0.0
        self._locked_on: date | None = None
        self._daily_frames: dict[str, DataFrame] = {}
        self._large_symbols: list[str] = []
        self._liquid_symbols: list[str] = []
        self._prepared_on: date | None = None
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
            holding.entry = float(price)
            holding.risk = abs(holding.entry - holding.stop)
            holding.highest = holding.entry
            holding.lowest = holding.entry
            holding.original_quantity = abs(float(quantity))
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
                self._protect(holding, float(quantity))
            return
        self._closing.discard(asset)
        remaining = abs(float(getattr(position, "quantity", 0.0)))
        if remaining <= 0:
            self._release(asset)
        elif asset in self._holdings:
            self._protect(self._holdings[asset], remaining)

    def _event(self, key: str, level: str, message: str) -> None:
        if key in self._events:
            return
        self._events.add(key)
        if self.exporter is not None:
            self.exporter.publish("running", key, cast(Any, level), message)

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

    def _prepare(self, day: date) -> None:
        if self._prepared_on == day:
            return
        try:
            large, liquid = self._universe()
            symbols = sorted(set(large).union({"SPY", "QQQ"}))
            self._daily_frames = self._frames(
                symbols,
                datetime.combine(day - timedelta(days=390), time(), TRADING_ZONE),
                cast(TimeFrame, TimeFrame.Day),
            )
            spx = self._spx(day)
            if spx is not None:
                self._daily_frames["^GSPC"] = spx
        except Exception as error:
            self._daily_frames = {}
            self._event("universe", "error", f"Stock universe unavailable: {type(error).__name__}")
            large, liquid = [], []
        self._large_symbols = large
        self._liquid_symbols = liquid
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
            frame.columns = [str(column).lower() for column in frame.columns]
            return cast(DataFrame, _clock(frame))
        except Exception as error:
            self._event("spx", "error", f"SPX market state unavailable: {type(error).__name__}")
            return None

    def _universe(self) -> tuple[list[str], list[str]]:
        try:
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
            large = sorted(
                symbol
                for symbol, cap, volume in rows
                if symbol in assets and cap >= 5e8 and volume >= 1e6
            )
            liquid = sorted(
                symbol
                for symbol, cap, volume in rows
                if symbol in assets and cap >= 5e8 and volume >= 1e6
            )
            UNIVERSE_CACHE.write_text(json.dumps({"large": large, "liquid": liquid}))
            return large, liquid
        except Exception:
            cached = json.loads(UNIVERSE_CACHE.read_text())
            return list(cached["large"]), list(cached["liquid"])

    def _frames(
        self, symbols: list[str], start: datetime, timeframe: TimeFrame, end: datetime | None = None
    ) -> dict[str, Any]:
        frames: dict[str, Any] = {}
        for offset in range(0, len(symbols), 50):
            request = StockBarsRequest(
                symbol_or_symbols=symbols[offset : offset + 50],
                start=start.astimezone(UTC),
                end=None if end is None else end.astimezone(UTC),
                timeframe=timeframe,
                adjustment=Adjustment.ALL,
                feed=DataFeed.IEX,
            )
            values = cast(Any, self._data.get_stock_bars(request)).df
            if values.empty:
                continue
            for symbol in values.index.get_level_values("symbol").unique():
                frames[str(symbol)] = _clock(values.xs(symbol, level="symbol"))
        return frames

    def _completed(self, frame: Any, now: datetime, minutes: int = 0) -> Any:
        values = _clock(frame)
        if minutes:
            return values[values.index + timedelta(minutes=minutes) <= now]
        return values[values.index.date < now.date()]

    def _run_daily(self, now: datetime) -> None:
        market = cast(
            DataFrame,
            self._completed(self._daily_frames.get("^GSPC", DataFrame()), now),
        )
        if not market_is_rising(market):
            self._event("market-state", "warning", "SPX is not above its 20-day average")
            self._daily_run_on = now.date()
            return
        for engine in self._selected:
            if engine == "sma":
                self._run_sma(now)
            if engine == "tfb_50":
                self._run_tfb(now)
        self._daily_run_on = now.date()

    def _run_sma(self, now: datetime) -> None:
        for symbol in self._large_symbols:
            frame = cast(
                DataFrame,
                self._completed(self._daily_frames.get(symbol, DataFrame()), now),
            )
            if self._claimed(symbol) or not momentum_entry(frame):
                continue
            try:
                blocked = earnings_blocked(symbol, now.date())
            except Exception as error:
                self._event(
                    f"earnings-{symbol}",
                    "error",
                    f"Earnings calendar unavailable for {symbol}: {type(error).__name__}",
                )
                continue
            if blocked:
                continue
            last = float(cast(Any, frame["close"]).iloc[-1])
            self._enter("sma", symbol, symbol, last, last - 1.5 * latest_atr(frame), now)

    def _run_tfb(self, now: datetime) -> None:
        for symbol in self._large_symbols:
            frame = cast(
                DataFrame,
                self._completed(self._daily_frames.get(symbol, DataFrame()), now),
            )
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
            or not opening_end <= now.time() <= time(10, 30)
            or not self._liquid_symbols
        ):
            return
        frames = self._intraday(self._liquid_symbols, now, minutes)
        for symbol in self._liquid_symbols:
            key = (now.date(), engine, symbol)
            frame = cast(Any, frames.get(symbol))
            if (
                key in self._orb_scanned
                or frame is None
                or frame.empty
                or self._claimed(symbol)
            ):
                continue
            opening = frame.between_time("09:30", "09:34" if minutes == 5 else "09:39")
            candle = frame.iloc[-1]
            if opening.empty or frame.index[-1].time() < opening_end:
                continue
            high = float(opening["high"].max())
            low = float(opening["low"].min())
            close = float(candle["close"])
            direction: Direction | None = 1 if close > high else -1 if close < low else None
            if direction is None:
                continue
            self._orb_scanned.add(key)
            if not self._orb_confirm(
                symbol,
                now,
                minutes,
                volume_multiple,
                direction,
                uses_macd,
            ):
                continue
            span = high - low
            stop = low + span * (0.75 if direction == 1 else 0.25)
            targets = None
            if minutes == 10:
                targets = (
                    high + 0.5 * span,
                    high + span,
                    high + 2.0 * span,
                ) if direction == 1 else (
                    low - 0.5 * span,
                    low - span,
                    low - 2.0 * span,
                )
            self._enter(
                engine,
                symbol,
                symbol,
                close,
                stop,
                now,
                direction=direction,
                targets=targets,
                risk_fraction_max=0.01 if engine == "orb" else None,
            )

    def _intraday(
        self, symbols: list[str], now: datetime, minutes: int
    ) -> dict[str, Any]:
        start = datetime.combine(now.date(), time(9, 30), TRADING_ZONE)
        timeframe = FIVE_MINUTES if minutes == 5 else TEN_MINUTES
        return {
            symbol: self._completed(frame, now, minutes)
            for symbol, frame in self._frames(symbols, start, timeframe, now).items()
        }

    def _orb_confirm(
        self,
        symbol: str,
        now: datetime,
        minutes: int,
        volume_multiple: float,
        direction: Direction,
        uses_macd: bool,
    ) -> bool:
        timeframe = FIVE_MINUTES if minutes == 5 else TEN_MINUTES
        frame = self._frames([symbol], now - timedelta(days=45), timeframe, now).get(symbol)
        if frame is None:
            return False
        completed = self._completed(frame, now, minutes)
        if completed.empty:
            return False
        if not relative_volume_ready(
            cast(DataFrame, completed),
            now.date(),
            completed.index[-1].time(),
            volume_multiple,
        ):
            return False
        if not uses_macd:
            return True
        return does_macd_confirm(completed["close"], direction)

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
            )
            exit_for_earnings = False
        if exit_for_earnings and now.time() >= time(15, 50):
            self._exit(holding)
            return
        frame = cast(
            DataFrame,
            self._completed(self._daily_frames.get(holding.signal, DataFrame()), now),
        )
        if len(frame) < 20:
            return
        values = cast(Any, frame)
        since = values[values.index >= holding.entered_at.astimezone(TRADING_ZONE)]
        observed = since if len(since) else values
        last = float(values["close"].iloc[-1])
        holding.highest = max(holding.highest, float(observed["close"].max()))
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
        recent = self._frames(
            [holding.signal], now - timedelta(days=5), timeframe, now
        ).get(holding.signal)
        if recent is None:
            return
        frame = cast(DataFrame, self._completed(recent, now, minutes))
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
        if (
            engine not in self._enabled
            or self._claimed(signal)
            or direction * (price - stop) <= 0
        ):
            return False
        if direction == -1:
            security = self.broker.api.get_asset(asset)
            if not bool(security.shortable):
                self._event(
                    f"short-{asset}-{now.date()}",
                    "warning",
                    f"Short entry skipped for {asset}: security is not shortable",
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
        if self._stops.get(holding.asset) == stop:
            return
        self._cancel(holding.asset)
        order = self.create_order(
            holding.asset,
            quantity_value(amount, bool(self.parameters["fractional_orders"])),
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
        self._stops[holding.asset] = stop

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
        return f"mt-{ENGINE_CODES[engine]}-{kind}-{signal}-{scaled}-{uuid4().hex[:8]}"

    def _order_engine(self, value: str) -> StrategyName | None:
        parts = value.split("-")
        return CODES_ENGINE.get(parts[1]) if len(parts) == 6 and parts[0] == "mt" else None

    def _order_signal(self, value: str) -> str | None:
        parts = value.split("-")
        return parts[3] if len(parts) == 6 and parts[0] == "mt" else None

    def _order_risk(self, value: str) -> float | None:
        parts = value.split("-")
        return int(parts[4]) / 1_000_000 if self._order_engine(value) is not None else None
