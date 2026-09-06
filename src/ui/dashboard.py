import asyncio
import hashlib
import time
from collections import OrderedDict
from datetime import UTC, date, datetime, timedelta
from datetime import time as dtime
from pathlib import Path
from typing import Annotated, Any, Literal, NotRequired, TypedDict, cast

import httpx
from fastapi import APIRouter, Query, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from itsdangerous import BadSignature, SignatureExpired, TimestampSigner
from pandas import DataFrame, DatetimeIndex, Timedelta
from pydantic import ValidationError
from starlette.responses import FileResponse

from bot.exchange import TRADING_ZONE, session_bounds, session_starts
from bot.frames import regular_session
from bot.indicators import PERIOD, latest_atr
from bot.strategies.breakout import Breakout, range_marks, range_stop
from bot.strategies.daily import Daily
from bot.strategies.registry import strategy_class
from bot.types import (
    POSITION_FRACTION_CAP,
    STATE_SIGNATURE_SALT,
    Direction,
    StateEvent,
    StateSnapshot,
    StrategyName,
    TradingConfiguration,
    is_strategy_name,
)

from .alpaca import AlpacaMarketDataClient, AlpacaReadClient, Bar, EquityPoint, Position
from .config import WebSettings
from .ledger import (
    UNATTRIBUTED,
    Cycle,
    FillRow,
    OpenCycle,
    Session,
    Totals,
    Unattributed,
    match_cycles,
    parse_day,
    sessions,
    strategy_labels,
    totals,
)
from .strategies import EntryWindow, entry_windows, strategy_rules


class BarRow(TypedDict):
    t: str
    o: float
    h: float
    l: float  # noqa: E741
    c: float
    v: float


class OpeningRange(TypedDict):
    high: float
    mid: float
    low: float


class BreakoutLevels(TypedDict):
    range: OpeningRange
    stop: float
    targets: list[float]


class Levels(TypedDict):
    strategy: str
    reconstructed: bool
    range: NotRequired[OpeningRange]
    stop: NotRequired[float]
    targets: NotRequired[list[float]]
    atr: NotRequired[float]


class TimeframeRules(TypedDict):
    bar: str
    pad_days: int
    span_max: int
    warmup_days: int


class BotState(TypedDict):
    status: str
    stale: bool
    running: bool
    reported: bool
    strategies: list[str]
    paused: list[str]
    events: list[StateEvent]


class PulsePosition(TypedDict):
    symbol: str
    side: str
    qty: float
    entry: float
    last: float
    value: float
    unreal: float
    unrealPct: float
    weight: float


class PositionRow(PulsePosition):
    strategy: str
    opened: str
    inDate: str | None
    inMinute: int | None
    fills: list[FillRow]


class EquityDay(TypedDict):
    date: str
    equity: float


class IntradayPoint(TypedDict):
    t: str
    equity: float


class BenchmarkClose(TypedDict):
    date: str
    close: float


class Pulse(TypedDict):
    asOf: str
    equity: float
    cash: float
    buyingPower: float
    marketValue: float
    unrealised: float
    positions: list[PulsePosition]


class Ledger(TypedDict):
    asOf: str
    today: str
    accountNumber: str
    status: str
    marketOpen: bool
    nextOpen: str
    invested: float
    funded: str
    equity: float
    lastEquity: float
    cash: float
    buyingPower: float
    marketValue: float
    unrealised: float
    positionCapPct: float
    dailyLossLimitPct: float
    bot: BotState
    strategies: list[dict[str, str]]
    windows: dict[str, EntryWindow]
    positions: list[PositionRow]
    trades: list[Cycle]
    days: list[Session]
    totals: Totals
    equityDaily: list[EquityDay]
    intraday: list[IntradayPoint]
    intradayDate: str
    spy: list[BenchmarkClose]


class ReadCache[Payload]:
    def __init__(self, ttl_seconds: int) -> None:
        self._ttl = ttl_seconds
        self._lock = asyncio.Lock()
        self._payload: Payload | None = None
        self._stamped_at = 0.0

    def fresh(self) -> Payload | None:
        if self._payload is None or time.monotonic() - self._stamped_at > self._ttl:
            return None
        return self._payload

    def store(self, payload: Payload) -> None:
        self._payload = payload
        self._stamped_at = time.monotonic()

    def drop(self) -> None:
        self._payload = None

    @property
    def lock(self) -> asyncio.Lock:
        return self._lock


class KeyedCache[Value]:
    def __init__(self, ttl_seconds: int, entries_max: int) -> None:
        self._ttl = ttl_seconds
        self._entries_max = entries_max
        self._entries: OrderedDict[str, tuple[float, Value]] = OrderedDict()
        self._lock = asyncio.Lock()

    def fresh(self, key: str) -> Value | None:
        entry = self._entries.get(key)
        if entry is None or time.monotonic() - entry[0] > self._ttl:
            return None
        self._entries.move_to_end(key)
        return entry[1]

    def store(self, key: str, value: Value) -> None:
        self._entries[key] = (time.monotonic(), value)
        self._entries.move_to_end(key)
        while len(self._entries) > self._entries_max:
            self._entries.popitem(last=False)

    @property
    def lock(self) -> asyncio.Lock:
        return self._lock


class StateStore:
    def __init__(self) -> None:
        self._snapshot: StateSnapshot | None = None

    def publish(self, snapshot: StateSnapshot) -> bool:
        current = self._snapshot
        if current is not None:
            if snapshot.run_id == current.run_id and snapshot.sequence <= current.sequence:
                return False
            if snapshot.run_id != current.run_id and snapshot.started_at <= current.started_at:
                return False
        self._snapshot = snapshot
        return True

    def read(self) -> StateSnapshot | None:
        return self._snapshot


ASSET_DIRECTORY = Path(__file__).with_name("assets")
DASHBOARD_HTML = (ASSET_DIRECTORY / "dashboard.html").read_bytes()
ASSET_MEDIA_TYPES = {
    "dashboard.css": "text/css",
    "dashboard.js": "text/javascript",
    "theme.js": "text/javascript",
    "favicon.svg": "image/svg+xml",
}
LEDGER_TTL_SECONDS = 60
PULSE_TTL_SECONDS = 2
BENCHMARK_SYMBOL = "SPY"
NO_STORE = {"Cache-Control": "no-store"}
IMMUTABLE = {"Cache-Control": "public, max-age=31536000, immutable"}
HEARTBEAT_TIMEOUT = timedelta(seconds=15)
SIGNATURE_WINDOW_SECONDS = 30
STATE_BODY_BYTES_MAX = 65_536
STATE_SIGNATURE_ENVELOPE_BYTES = 51
STATE_REQUEST_BYTES_MAX = STATE_BODY_BYTES_MAX + STATE_SIGNATURE_ENVELOPE_BYTES
CHART_TIMEFRAMES: dict[str, TimeframeRules] = {
    "5Min": {"bar": "5Min", "pad_days": 1, "span_max": 10, "warmup_days": 5},
    "1Hour": {"bar": "1Hour", "pad_days": 7, "span_max": 90, "warmup_days": 46},
    "1Day": {"bar": "1Day", "pad_days": 120, "span_max": 900, "warmup_days": 300},
}
SMA_LENGTHS = (20, 50, 200)
CHART_TTL_SECONDS = 120
CHART_CACHE_MAX = 64
SESSION_SOURCE = "30Min"
SESSION_SOURCE_BARS_MAX = 1000
LEVELS_HISTORY_DAYS = 90
DASHBOARD_HEADERS = {
    "Cache-Control": "private, no-cache",
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; "
        "style-src 'self' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; "
        "connect-src 'self'; img-src 'self' data:; "
        "object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
    ),
}


def session_hour_bars(bars: list[Bar]) -> list[BarRow]:
    if not bars:
        return []
    frame = _bar_frame(bars)
    regular = regular_session(frame)
    if regular.empty:
        return []
    index = cast(DatetimeIndex, regular.index)
    starts = session_starts(index)
    elapsed = (index - starts) // Timedelta(hours=1)
    folded = (
        cast(Any, regular)
        .groupby(starts + elapsed * Timedelta(hours=1))
        .agg(o=("o", "first"), h=("h", "max"), l=("l", "min"), c=("c", "last"), v=("v", "sum"))
    )
    return [
        {
            "t": start.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            "o": float(row.o),
            "h": float(row.h),
            "l": float(row.l),
            "c": float(row.c),
            "v": float(row.v),
        }
        for start, row in folded.iterrows()
    ]


def chart_window(timeframe: str, opened: date, closed: date) -> tuple[datetime, datetime, datetime]:
    rules = CHART_TIMEFRAMES[timeframe]
    pad = timedelta(days=rules["pad_days"])
    display = opened - pad
    end = closed + pad
    if (end - display).days > rules["span_max"]:
        display = end - timedelta(days=rules["span_max"])
    data = display - timedelta(days=rules["warmup_days"])
    return (
        datetime.combine(data, dtime(0, 0), TRADING_ZONE),
        datetime.combine(display, dtime(0, 0), TRADING_ZONE),
        datetime.combine(end, dtime(23, 59), TRADING_ZONE),
    )


def bars_atr(bars: list[Bar]) -> float | None:
    if len(bars) <= PERIOD:
        return None
    frame = _bar_frame(bars).rename(columns={"h": "high", "l": "low", "c": "close"})
    return latest_atr(frame)


def opening_range(bars: list[Bar], opens: datetime, minutes: int) -> tuple[float, float] | None:
    closes = opens + timedelta(minutes=minutes)
    inside = [bar for bar in bars if opens <= _bar_time(bar) < closes]
    if not inside:
        return None
    return max(bar.high for bar in inside), min(bar.low for bar in inside)


def breakout_levels(
    strategy: type[Breakout], direction: Direction, entry: float, high: float, low: float
) -> BreakoutLevels:
    stop = range_stop(direction, high, low)
    targets = strategy.target_prices(entry, stop, direction)
    marks = range_marks(high, low)
    return BreakoutLevels(
        range=OpeningRange(
            high=round(marks.high, 4), mid=round(marks.mid, 4), low=round(marks.low, 4)
        ),
        stop=round(stop, 4),
        targets=[round(value, 4) for value in targets],
    )


def error_response(
    detail: str, status_code: int, headers: dict[str, str] | None = None
) -> JSONResponse:
    return JSONResponse(
        {"detail": detail}, status_code=status_code, headers={**NO_STORE, **(headers or {})}
    )


def read_response(data: Any, max_age: int, **metadata: Any) -> JSONResponse:
    content = {"data": data, "read_at": datetime.now(UTC), **metadata}
    return JSONResponse(
        jsonable_encoder(content),
        headers={"Cache-Control": f"private, max-age={max_age}, must-revalidate", "Vary": "Cookie"},
    )


async def build_ledger(
    alpaca: AlpacaReadClient,
    market: AlpacaMarketDataClient,
    fallback_configuration: TradingConfiguration,
    snapshot: StateSnapshot | None,
    stale: bool,
) -> Ledger:
    async with asyncio.TaskGroup() as reads:
        account_read = reads.create_task(alpaca.account())
        positions_read = reads.create_task(alpaca.raw_positions())
        fills_read = reads.create_task(alpaca.raw_fills())
        orders_read = reads.create_task(alpaca.raw_closed_orders())
        daily_read = reads.create_task(alpaca.equity("1A", "1D"))
        intraday_read = reads.create_task(alpaca.equity("1D", "5Min"))
        clock_read = reads.create_task(alpaca.clock())

    account = account_read.result()
    positions = positions_read.result()
    clock = clock_read.result()

    cycles, open_cycles = match_cycles(fills_read.result(), orders_read.result())
    equity_daily = _equity_series(daily_read.result())
    intraday_points, intraday_date = _intraday_series(intraday_read.result())

    invested = equity_daily[0]["equity"] if equity_daily else account.equity
    funded = equity_daily[0]["date"] if equity_daily else ""
    equity = round(account.equity, 2)
    closes = {row["date"]: row["equity"] for row in equity_daily}

    today = datetime.now(TRADING_ZONE).date().isoformat()
    if not equity_daily or equity_daily[-1]["date"] != today:
        equity_daily.append(EquityDay(date=today, equity=equity))

    rows = _position_rows(positions, equity, open_cycles)
    configuration = snapshot.configuration if snapshot else fallback_configuration
    benchmark_start = funded or today

    try:
        bars = await market.daily_bars(BENCHMARK_SYMBOL, benchmark_start)
    except httpx.HTTPError:
        bars = []

    return Ledger(
        asOf=datetime.now(TRADING_ZONE).strftime("%a %-d %b %Y, %H:%M:%S ET"),
        today=today,
        accountNumber=account.account_number,
        status=account.status,
        marketOpen=clock.is_open,
        nextOpen=datetime.fromisoformat(clock.next_open).strftime("%H:%M ET"),
        invested=invested,
        funded=datetime.fromisoformat(funded).strftime("%-d %b %Y") if funded else "—",
        equity=equity,
        lastEquity=round(account.last_equity, 2),
        cash=round(account.cash, 2),
        buyingPower=round(account.buying_power, 2),
        marketValue=round(sum(row["value"] for row in rows), 2),
        unrealised=round(sum(row["unreal"] for row in rows), 2),
        positionCapPct=round(
            100
            * min(
                POSITION_FRACTION_CAP,
                configuration.position_fraction_max,
            ),
            2,
        ),
        dailyLossLimitPct=round(100 * configuration.risk_per_day_max, 2),
        bot=bot_state(snapshot, stale),
        strategies=strategy_labels(),
        windows=entry_windows(),
        positions=rows,
        trades=cycles,
        days=sessions(cycles, closes, invested),
        totals=totals(cycles),
        equityDaily=equity_daily,
        intraday=intraday_points,
        intradayDate=intraday_date,
        spy=[BenchmarkClose(date=bar.at[:10], close=bar.close) for bar in bars],
    )


async def build_pulse(alpaca: AlpacaReadClient) -> Pulse:
    async with asyncio.TaskGroup() as reads:
        account_read = reads.create_task(alpaca.account())
        positions_read = reads.create_task(alpaca.raw_positions())

    account = account_read.result()
    positions = positions_read.result()
    equity = round(account.equity, 2)
    held = _pulse_positions(positions, equity)
    return Pulse(
        asOf=datetime.now(TRADING_ZONE).strftime("%a %-d %b %Y, %H:%M:%S ET"),
        equity=equity,
        cash=round(account.cash, 2),
        buyingPower=round(account.buying_power, 2),
        marketValue=round(sum(row["value"] for row in held), 2),
        unrealised=round(sum(row["unreal"] for row in held), 2),
        positions=held,
    )


def bot_state(snapshot: StateSnapshot | None, stale: bool) -> BotState:
    running = snapshot is not None and snapshot.status == "running" and not stale
    return BotState(
        status=snapshot.status if snapshot else "unknown",
        stale=stale,
        running=running,
        reported=snapshot is not None,
        strategies=list(snapshot.strategies) if snapshot else [],
        paused=list(snapshot.paused) if snapshot else [],
        events=list(reversed(snapshot.events)) if snapshot else [],
    )


def dashboard_router(configuration: WebSettings, state_store: StateStore) -> APIRouter:
    router = APIRouter()
    mode = configuration.broker_mode.upper().encode()
    dashboard_html = DASHBOARD_HTML.replace(b"{{ BROKER_MODE }}", mode)
    for plain, fingerprinted in ASSET_REWRITES.items():
        dashboard_html = dashboard_html.replace(plain, fingerprinted)
    signer = TimestampSigner(
        configuration.state_export_secret.get_secret_value(),
        salt=STATE_SIGNATURE_SALT,
        digest_method=hashlib.sha256,
    )

    ledger_cache = ReadCache[Ledger](LEDGER_TTL_SECONDS)
    pulse_cache = ReadCache[Pulse](PULSE_TTL_SECONDS)
    bar_cache = KeyedCache[list[BarRow]](CHART_TTL_SECONDS, CHART_CACHE_MAX)
    levels_cache = KeyedCache[Levels](CHART_TTL_SECONDS, CHART_CACHE_MAX)

    def alpaca(request: Request) -> AlpacaReadClient:
        return request.state.alpaca

    def market(request: Request) -> AlpacaMarketDataClient:
        return request.state.market

    def read_state() -> tuple[StateSnapshot | None, bool]:
        snapshot = state_store.read()
        stale = snapshot is None or datetime.now(UTC) - snapshot.heartbeat_at > HEARTBEAT_TIMEOUT
        return snapshot, stale

    @router.get("/")
    async def dashboard() -> Response:
        return Response(dashboard_html, media_type="text/html", headers=DASHBOARD_HEADERS)

    @router.get("/assets/{filename}")
    async def asset(filename: str) -> Response:
        served = ASSET_ROUTES.get(filename)
        if served is None:
            return error_response("Asset was not found", 404)
        path, media_type = served
        return FileResponse(path, media_type=media_type, headers=IMMUTABLE)

    @router.get("/api/session")
    async def session(request: Request) -> JSONResponse:
        token = request.session.get("csrf_token")
        if not isinstance(token, str):
            return error_response("Session is invalid", 401)
        return JSONResponse({"csrf_token": token}, headers=NO_STORE)

    @router.get("/api/bars")
    async def bars(
        request: Request,
        symbol: Annotated[str, Query(min_length=1, max_length=12, pattern=r"^[A-Z][A-Z.]*$")],
        timeframe: Annotated[Literal["5Min", "1Hour", "1Day"], Query()],
        opened: Annotated[str, Query(pattern=r"^\d{4}-\d{2}-\d{2}$")],
        closed: Annotated[str, Query(pattern=r"^\d{4}-\d{2}-\d{2}$")],
    ) -> JSONResponse:
        try:
            opened_on, closed_on = parse_day(opened), parse_day(closed)
        except ValueError:
            return error_response("Dates are invalid", 422)
        if closed_on < opened_on:
            return error_response("The close cannot precede the open", 422)

        start, display, end = chart_window(timeframe, opened_on, closed_on)
        key = f"{symbol}|{timeframe}|{start.isoformat()}|{end.isoformat()}"
        cached = bar_cache.fresh(key)
        if cached is None:
            async with bar_cache.lock:
                cached = bar_cache.fresh(key)
                if cached is None:
                    if timeframe == "1Hour":
                        half = await market(request).bars_paged(
                            symbol,
                            SESSION_SOURCE,
                            start.isoformat(),
                            end.isoformat(),
                            limit=SESSION_SOURCE_BARS_MAX,
                        )
                        cached = session_hour_bars(half)
                    else:
                        cached = [
                            _bar_row(bar)
                            for bar in await market(request).bars(
                                symbol,
                                CHART_TIMEFRAMES[timeframe]["bar"],
                                start.isoformat(),
                                end.isoformat(),
                            )
                        ]
                    bar_cache.store(key, cached)
        return read_response(
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "displayFrom": display.isoformat(),
                "smaLengths": list(SMA_LENGTHS),
                "bars": cached,
            },
            60,
        )

    @router.get("/api/levels")
    async def levels(
        request: Request,
        symbol: Annotated[str, Query(min_length=1, max_length=12, pattern=r"^[A-Z][A-Z.]*$")],
        strategy: Annotated[StrategyName | Unattributed, Query()],
        side: Annotated[Literal["long", "short"], Query()],
        entry: Annotated[float, Query(gt=0)],
        opened: Annotated[str, Query(pattern=r"^\d{4}-\d{2}-\d{2}$")],
    ) -> JSONResponse:
        try:
            opened_on = parse_day(opened)
        except ValueError:
            return error_response("The open date is invalid", 422)

        key = f"levels|{symbol}|{strategy}|{side}|{entry}|{opened}"
        cached = levels_cache.fresh(key)
        if cached is not None:
            return read_response(cached, 300)

        direction: Direction = 1 if side == "long" else -1
        payload = Levels(strategy=strategy, reconstructed=True)
        bounds = session_bounds(opened_on)
        found_class = strategy_class(strategy) if is_strategy_name(strategy) else None

        async with levels_cache.lock:
            if found_class is not None and issubclass(found_class, Breakout) and bounds:
                breakout = found_class
                opens = bounds[0]
                minutes = breakout.opening_minutes
                opening_bars = await market(request).bars(
                    symbol,
                    "5Min",
                    opens.isoformat(),
                    (opens + timedelta(minutes=3 * minutes)).isoformat(),
                    limit=10,
                )
                found = opening_range(opening_bars, opens, minutes)
                if found is not None:
                    levels = breakout_levels(breakout, direction, entry, *found)
                    payload["range"] = levels["range"]
                    payload["stop"] = levels["stop"]
                    payload["targets"] = levels["targets"]
            elif found_class is not None and issubclass(found_class, Daily):
                history = await market(request).bars(
                    symbol,
                    "1Day",
                    (opened_on - timedelta(days=LEVELS_HISTORY_DAYS)).isoformat(),
                    datetime.combine(opened_on, dtime(0, 0), TRADING_ZONE).isoformat(),
                    limit=LEVELS_HISTORY_DAYS,
                )
                average_range = bars_atr(history)
                if average_range is not None:
                    distance = found_class.stop_atr_multiple * average_range
                    payload["stop"] = round(entry - direction * distance, 4)
                    payload["atr"] = round(average_range, 4)
            levels_cache.store(key, payload)
        return read_response(payload, 300)

    @router.get("/api/strategies")
    async def strategies() -> JSONResponse:
        snapshot, _ = read_state()
        reported = snapshot is not None
        active_configuration = (
            snapshot.configuration if snapshot else configuration.trading_configuration
        )
        return read_response(strategy_rules(active_configuration, configured=reported), 60)

    @router.get("/api/ledger")
    async def ledger(request: Request) -> JSONResponse:
        snapshot, stale = read_state()
        cached = ledger_cache.fresh()
        if cached is None:
            async with ledger_cache.lock:
                cached = ledger_cache.fresh()
                if cached is None:
                    cached = await build_ledger(
                        alpaca(request),
                        market(request),
                        configuration.trading_configuration,
                        snapshot,
                        stale,
                    )
                    ledger_cache.store(cached)
        return read_response({**cached, "bot": bot_state(snapshot, stale)}, 10)

    @router.get("/api/pulse")
    async def pulse(request: Request) -> JSONResponse:
        cached = pulse_cache.fresh()
        if cached is None:
            async with pulse_cache.lock:
                cached = pulse_cache.fresh()
                if cached is None:
                    cached = await build_pulse(alpaca(request))
                    pulse_cache.store(cached)

        held = ledger_cache.fresh()
        if held is not None and {row["symbol"] for row in held["positions"]} != {
            row["symbol"] for row in cached["positions"]
        }:
            ledger_cache.drop()

        return read_response(cached, 0)

    @router.post("/internal/state", status_code=204)
    async def publish_state(request: Request) -> Response:
        chunks: list[bytes] = []
        size = 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > STATE_REQUEST_BYTES_MAX:
                return error_response("State snapshot is too large", 413)
            chunks.append(chunk)
        try:
            body, signed_at = signer.unsign(
                b"".join(chunks),
                max_age=SIGNATURE_WINDOW_SECONDS,
                return_timestamp=True,
            )
        except SignatureExpired:
            return error_response("State signature has expired", 401)
        except BadSignature:
            return error_response("State signature is invalid", 401)
        if len(body) > STATE_BODY_BYTES_MAX:
            return error_response("State snapshot is too large", 413)
        try:
            snapshot = StateSnapshot.model_validate_json(body)
        except ValidationError:
            return error_response("State snapshot is invalid", 422)
        drift = abs((snapshot.heartbeat_at - signed_at).total_seconds())
        if snapshot.started_at > snapshot.heartbeat_at or drift > SIGNATURE_WINDOW_SECONDS:
            return error_response("State snapshot is invalid", 422)
        if not state_store.publish(snapshot):
            return error_response("State snapshot is not new", 409)
        return Response(status_code=204, headers=NO_STORE)

    return router


def _fingerprint_assets() -> tuple[dict[str, tuple[Path, str]], dict[bytes, bytes]]:
    routes: dict[str, tuple[Path, str]] = {}
    rewrites: dict[bytes, bytes] = {}
    for name, media_type in ASSET_MEDIA_TYPES.items():
        path = ASSET_DIRECTORY / name
        digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
        served = f"{path.stem}.{digest}{path.suffix}"
        routes[served] = (path, media_type)
        rewrites[f"/assets/{name}".encode()] = f"/assets/{served}".encode()
    return routes, rewrites


ASSET_ROUTES, ASSET_REWRITES = _fingerprint_assets()


def _bar_time(bar: Bar) -> datetime:
    return datetime.fromisoformat(bar.at.replace("Z", "+00:00")).astimezone(TRADING_ZONE)


def _bar_row(bar: Bar) -> BarRow:
    return {
        "t": bar.at,
        "o": bar.open,
        "h": bar.high,
        "l": bar.low,
        "c": bar.close,
        "v": bar.volume,
    }


def _bar_frame(bars: list[Bar]) -> DataFrame:
    frame = DataFrame(
        {
            "o": [bar.open for bar in bars],
            "h": [bar.high for bar in bars],
            "l": [bar.low for bar in bars],
            "c": [bar.close for bar in bars],
            "v": [bar.volume for bar in bars],
        },
        index=DatetimeIndex([_bar_time(bar) for bar in bars], tz=TRADING_ZONE),
    )
    return frame.sort_index()


def _funded_points(points: list[EquityPoint]) -> list[tuple[datetime, float]]:
    return [
        (datetime.fromtimestamp(point.timestamp, TRADING_ZONE), point.equity)
        for point in points
        if point.equity
    ]


def _equity_series(points: list[EquityPoint]) -> list[EquityDay]:
    return [
        EquityDay(date=when.date().isoformat(), equity=round(value, 2))
        for when, value in _funded_points(points)
    ]


def _intraday_series(points: list[EquityPoint]) -> tuple[list[IntradayPoint], str]:
    funded = _funded_points(points)
    rows = [
        IntradayPoint(t=when.strftime("%H:%M"), equity=round(value, 2)) for when, value in funded
    ]
    return rows, funded[0][0].date().isoformat() if funded else ""


def _pulse_positions(raw: list[Position], equity: float) -> list[PulsePosition]:
    rows = [
        PulsePosition(
            symbol=item.symbol,
            side="long" if item.side == "long" else "short",
            qty=round(abs(item.qty), 4),
            entry=round(item.avg_entry_price, 4),
            last=round(item.current_price, 4),
            value=round(item.market_value, 2),
            unreal=round(item.unrealized_pl, 2),
            unrealPct=round(item.unrealized_plpc * 100, 2),
            weight=round(item.market_value / equity * 100, 2) if equity else 0.0,
        )
        for item in raw
    ]
    rows.sort(key=lambda row: -row["value"])
    return rows


def _position_rows(
    raw: list[Position],
    equity: float,
    open_cycles: dict[str, OpenCycle],
) -> list[PositionRow]:
    rows: list[PositionRow] = []
    for position in _pulse_positions(raw, equity):
        held = open_cycles.get(position["symbol"])
        rows.append(
            PositionRow(
                **position,
                strategy=held["strategy"] if held else UNATTRIBUTED,
                opened=held["opened"] if held else "—",
                inDate=held["inDate"] if held else None,
                inMinute=held["inMinute"] if held else None,
                fills=held["fills"] if held else [],
            )
        )
    return rows
