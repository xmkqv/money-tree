import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_DOWN, Decimal
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
from pandas import DataFrame, Series

from bot.config import settings
from bot.strategies.shared import StrategyBase
from bot.strategies.sma import adx, entry_quantity, rsi, true_range, wilder
from bot.types import StrategyName


TRADING_ZONE = ZoneInfo("America/New_York")
FIVE_MINUTES = TimeFrame(5, cast(TimeFrameUnit, TimeFrameUnit.Minute))
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


def _swing_low(low: Any) -> float | None:
    values = [float(value) for value in low]
    return next(
        (
            values[index]
            for index in range(len(values) - 3, 1, -1)
            if values[index] < min(values[index - 2 : index])
            and values[index] < min(values[index + 1 : index + 3])
        ),
        None,
    )


def _atr(frame: Any) -> float:
    return float(
        cast(
            Any,
            wilder(
                true_range(
                    cast(Series, frame["high"]),
                    cast(Series, frame["low"]),
                    cast(Series, frame["close"]),
                ),
                14,
            ),
        ).iloc[-1]
    )


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
        self._orb_scanned: set[tuple[date, str]] = set()
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
        if "buy" in side and (pending := self._pending.pop(asset, None)) is not None:
            holding = pending.holding
            fraction = holding.risk / holding.entry
            holding.entry = float(price)
            holding.risk = holding.entry * fraction
            holding.stop = holding.entry - holding.risk
            holding.highest = holding.entry
            self._holdings[asset] = holding
            self._protect(holding, float(quantity))
        if "sell" in side:
            self._closing.discard(asset)
            remaining = abs(float(getattr(position, "quantity", 0.0)))
            if remaining <= 0:
                self._release(asset)

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
            if match is None or float(position.qty) <= 0:
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
            holding = Holding(engine, signal, asset, entry, entry - risk, risk, entry, entered_at)
            initial_quantity = float(entry_order.filled_qty or entry_order.qty or position.qty)
            remaining_fraction = float(position.qty) / initial_quantity
            if engine == "orb" and remaining_fraction <= 0.5:
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
        except Exception as error:
            self._daily_frames = {}
            self._event("universe", "error", f"Stock universe unavailable: {type(error).__name__}")
            large, liquid = [], []
        self._large_symbols = large
        self._liquid_symbols = liquid
        self._prepared_on = day

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
            large = sorted(symbol for symbol, cap, _ in rows if symbol in assets and cap >= 2e9)
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
        for engine in self._selected:
            if engine == "sma":
                self._run_sma(now)
            if engine == "tfb_50":
                self._run_tfb(now)
        self._daily_run_on = now.date()

    def _run_sma(self, now: datetime) -> None:
        for symbol in self._large_symbols:
            frame = self._completed(self._daily_frames.get(symbol, DataFrame()), now)
            if len(frame) < 205 or self._claimed(symbol):
                continue
            close = frame["close"]
            high = frame["high"]
            low = frame["low"]
            sma20 = close.rolling(20).mean()
            last = float(close.iloc[-1])
            crossed = float(close.iloc[-2]) < float(sma20.iloc[-2]) and last > float(sma20.iloc[-1])
            strength = float(cast(Any, rsi(close, 14)).iloc[-1])
            trend = (
                last
                > float(close.rolling(50).mean().iloc[-1])
                > float(close.rolling(200).mean().iloc[-1])
            )
            stop = _swing_low(low)
            if (
                crossed
                and trend
                and 50 <= strength <= 70
                and float(cast(Any, adx(high, low, close, 14)).iloc[-1]) > 25
                and stop is not None
            ):
                self._enter("sma", symbol, symbol, last, stop, now)

    def _run_tfb(self, now: datetime) -> None:
        for symbol in sorted(set(self._large_symbols).union({"SPY", "QQQ"})):
            frame = self._completed(self._daily_frames.get(symbol, DataFrame()), now)
            if len(frame) < 55 or self._claimed(symbol):
                continue
            close = frame["close"]
            sma50 = close.rolling(50).mean()
            stop = _swing_low(frame["low"])
            rising = all(
                float(sma50.iloc[index]) > float(sma50.iloc[index - 1]) for index in (-1, -2, -3)
            )
            if (
                float(close.iloc[-1]) > float(sma50.iloc[-1])
                and rising
                and float(
                    cast(
                        Any,
                        adx(
                            cast(Series, frame["high"]),
                            cast(Series, frame["low"]),
                            close,
                            14,
                        ),
                    ).iloc[-1]
                )
                < 20
                and float(close.iloc[-1]) > float(frame["high"].iloc[-2])
                and stop is not None
            ):
                self._enter("tfb_50", symbol, symbol, float(close.iloc[-1]), stop, now)

    def _run_orb(self, now: datetime) -> None:
        if "orb" not in self._enabled or not time(9, 40) <= now.time() < time(15, 55):
            return
        key = (now.date(), "orb")
        if key in self._orb_traded:
            return
        frame = self._intraday(["SPY"], now).get("SPY")
        if frame is None or len(frame) < 3:
            return
        opening = frame.between_time("09:30", "09:39")
        candle = frame.iloc[-1]
        if len(opening) != 2 or frame.index[-1].time() < time(9, 40):
            return
        high = float(opening["high"].max())
        low = float(opening["low"].min())
        span = float(candle["high"] - candle["low"])
        close = float(candle["close"])
        if close > high and span > 0 and close >= float(candle["high"]) - span * 0.25:
            accepted = self._enter("orb", "SPY", "SPY", close, low, now, loss_max=0.80)
        elif close < low and span > 0 and close <= float(candle["low"]) + span * 0.25:
            proxy = float(self.get_last_price("SH"))
            risk_fraction = (high - close) / close
            accepted = self._enter(
                "orb", "SPY", "SH", proxy, proxy * (1 - risk_fraction), now, loss_max=0.80
            )
        else:
            accepted = False
        if accepted:
            self._orb_traded.add(key)

    def _run_orb_momentum(self, now: datetime) -> None:
        if (
            "orb_momentum" not in self._enabled
            or not time(9, 40) <= now.time() <= time(10, 30)
            or not self._liquid_symbols
        ):
            return
        frames = self._intraday(self._liquid_symbols, now)
        for symbol in self._liquid_symbols:
            key = (now.date(), symbol)
            frame = frames.get(symbol)
            if key in self._orb_scanned or frame is None or len(frame) < 3 or self._claimed(symbol):
                continue
            opening = frame.between_time("09:30", "09:39")
            if len(opening) != 2:
                continue
            close = frame["close"]
            last = float(close.iloc[-1])
            high = float(opening["high"].max())
            low = float(opening["low"].min())
            long = last > high
            short = last < low
            if not long and not short:
                continue
            self._orb_scanned.add(key)
            if not self._momentum_confirm(symbol, now, float(frame["volume"].sum()), long):
                continue
            if short:
                self._event(
                    f"short-{symbol}-{now.date()}",
                    "warning",
                    f"ORB Momentum short skipped for {symbol}: account cannot short",
                )
                continue
            self._enter("orb_momentum", symbol, symbol, last, low, now)

    def _intraday(self, symbols: list[str], now: datetime) -> dict[str, Any]:
        start = datetime.combine(now.date(), time(9, 30), TRADING_ZONE)
        return {
            symbol: self._completed(frame, now, 5)
            for symbol, frame in self._frames(symbols, start, FIVE_MINUTES, now).items()
        }

    def _momentum_confirm(self, symbol: str, now: datetime, current: float, long: bool) -> bool:
        frame = self._frames([symbol], now - timedelta(days=45), FIVE_MINUTES, now).get(symbol)
        daily = self._daily_frames.get(symbol)
        if frame is None or daily is None:
            return False
        history = _clock(frame).between_time("09:30", "15:59")
        macd = (
            history["close"].ewm(span=12, adjust=False).mean()
            - history["close"].ewm(span=26, adjust=False).mean()
        )
        if (float(macd.iloc[-1]) > float(macd.iloc[-2])) != long:
            return False
        clock = (now - timedelta(minutes=5)).time()
        totals = [
            float(group[group.index.time <= clock]["volume"].sum())
            for day, group in history.groupby(history.index.date)
            if day < now.date()
        ][-20:]
        volumes = self._completed(daily, now)["volume"].tail(20)
        return (
            len(totals) == 20
            and float(volumes.mean()) >= 1_000_000
            and current >= 1.5 * sum(totals) / len(totals)
        )

    def _manage(self, now: datetime) -> None:
        for holding in list(self._holdings.values()):
            if now.time() >= time(15, 55) and holding.engine in {"orb", "orb_momentum"}:
                self._exit(holding)
                continue
            if holding.engine in {"sma", "tfb_50"}:
                self._manage_daily(holding, now)
            elif holding.engine == "orb":
                self._manage_orb(holding)
            elif holding.engine == "orb_momentum":
                self._manage_orb_momentum(holding, now)

    def _manage_daily(self, holding: Holding, now: datetime) -> None:
        frame = self._completed(self._daily_frames.get(holding.signal, DataFrame()), now)
        if len(frame) < 22:
            return
        close = frame["close"]
        last = float(close.iloc[-1])
        sma20 = float(close.rolling(20).mean().iloc[-1])
        strength = float(cast(Any, rsi(close, 14)).iloc[-1])
        if holding.engine == "sma":
            since = frame[frame.index >= holding.entered_at.astimezone(TRADING_ZONE)]
            observed = since if len(since) else frame
            holding.highest = max(holding.highest, float(observed["high"].max()))
            holding.stop = max(holding.stop, holding.highest - 1.5 * _atr(frame))
            if last >= holding.entry + 2 * holding.risk or (last < sma20 and strength < 50):
                self._exit(holding)
                return
        else:
            swing = _swing_low(frame["low"])
            if swing is not None:
                holding.stop = max(holding.stop, swing)
            if last < float(frame["low"].iloc[-2]) or (last < sma20 and strength < 50):
                self._exit(holding)
                return
        self._protect(holding)

    def _manage_orb(self, holding: Holding) -> None:
        price = float(self.get_last_price(holding.asset))
        holding.highest = max(holding.highest, price)
        quantity = self._quantity(holding.asset)
        if holding.stage == 0 and price >= holding.entry + 2 * holding.risk:
            holding.stage = 1
            self._exit(holding, quantity * 0.5)
        elif holding.stage == 1 and price >= holding.entry + 3 * holding.risk:
            holding.stage = 2
            self._exit(holding, quantity * 0.5)
        elif holding.stage == 2 and price >= holding.entry + 4 * holding.risk:
            self._exit(holding)
        elif holding.stage >= 1:
            holding.stop = max(holding.stop, holding.highest - holding.risk)
            self._protect(holding)

    def _manage_orb_momentum(self, holding: Holding, now: datetime) -> None:
        recent = self._frames([holding.signal], now - timedelta(days=5), FIVE_MINUTES, now).get(
            holding.signal
        )
        if recent is None or len(recent) < 15:
            return
        frame = self._completed(recent, now, 5)
        session = frame[frame.index.date == now.date()]
        if len(session) < 3:
            return
        price = float(self.get_last_price(holding.asset))
        holding.highest = max(holding.highest, price)
        opening_high = float(session.between_time("09:30", "09:39")["high"].max())
        if float(session["close"].iloc[-1]) < opening_high:
            self._exit(holding)
            return
        if price >= holding.entry + holding.risk:
            holding.stage = 1
            holding.stop = max(holding.stop, holding.entry, holding.highest - 1.5 * _atr(frame))
        self._protect(holding)

    def _enter(
        self,
        engine: StrategyName,
        signal: str,
        asset: str,
        price: float,
        stop: float,
        now: datetime,
        loss_max: float | None = None,
    ) -> bool:
        if engine not in self._enabled or self._claimed(signal) or stop >= price:
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
        if loss_max is not None:
            risk_fraction = min(risk_fraction, loss_max / equity)
        quantity = entry_quantity(
            equity,
            price,
            price - stop,
            min(0.10, float(self.parameters["position_fraction_max"])),
            risk_fraction,
            bool(self.parameters["fractional_orders"]),
        )
        notional = float(quantity) * price
        if quantity <= 0 or gross + notional > equity:
            return False
        holding = Holding(
            engine, signal, asset, price, stop, price - stop, price, now.astimezone(UTC)
        )
        self._pending[asset] = Pending(holding, now, notional)
        self._claims[signal] = engine
        self._claims[asset] = engine
        order = self.create_order(
            asset,
            quantity,
            "buy",
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
        if stop >= price:
            self._exit(holding)
            return
        if self._stops.get(holding.asset) == stop:
            return
        self._cancel(holding.asset)
        order = self.create_order(
            holding.asset,
            self._quantity_value(amount),
            "sell",
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
        amount = self._quantity(holding.asset) if quantity is None else quantity
        if amount <= 0:
            self._release(holding.asset)
            return
        self._cancel(holding.asset)
        order = self.create_order(
            holding.asset,
            self._quantity_value(amount),
            "sell",
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
        canceled = False
        for order in cast(list[Any], self.get_orders()):
            if order.is_active() and str(order.asset.symbol) == asset:
                self.cancel_order(order)
                canceled = True
        if canceled:
            self.sleep(1)
        self._stops.pop(asset, None)

    def _quantity(self, asset: str) -> float:
        position = self.get_position(asset)
        return 0.0 if position is None else abs(float(position.quantity))

    def _quantity_value(self, quantity: float) -> Decimal:
        increment = Decimal("0.000000001" if self.parameters["fractional_orders"] else "1")
        return Decimal(str(quantity)).quantize(increment, rounding=ROUND_DOWN)

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
