import asyncio
import hashlib
import time
from collections import OrderedDict
from datetime import UTC, date, datetime, timedelta
from datetime import time as dtime
from pathlib import Path
from typing import Annotated, Any, Literal, cast

import httpx
from fastapi import APIRouter, Query, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from itsdangerous import BadSignature, SignatureExpired, TimestampSigner
from pandas import DataFrame, DatetimeIndex, Timedelta
from pydantic import ValidationError
from starlette.responses import FileResponse

from bot.strategies.daily_base import DAILY_STOP_ATR_MULTIPLES
from bot.strategies.orb_base import ORB_OPENING_MINUTES, ORB_TARGET_MULTIPLES, range_stop
from bot.strategies.shared import (
    PERIOD,
    TRADING_ZONE,
    Direction,
    latest_atr,
    regular_session,
    session_bounds,
    session_starts,
)
from bot.types import (
    POSITION_FRACTION_CAP_MAX,
    STATE_SIGNATURE_SALT,
    RuntimeSnapshot,
    TradingConfiguration,
)

from .alpaca import AlpacaMarketDataClient, AlpacaReadClient
from .config import WebSettings
from .ledger import match_cycles, parse_day, sessions, strategy_id, strategy_labels, totals
from .strategies import entry_windows, strategy_spec


class ReadCache:
    def __init__(self, ttl_seconds: int) -> None:
        self._ttl = ttl_seconds
        self._lock = asyncio.Lock()
        self._payload: dict[str, Any] | None = None
        self._stamped_at = 0.0

    def fresh(self) -> dict[str, Any] | None:
        if self._payload is None or time.monotonic() - self._stamped_at > self._ttl:
            return None
        return self._payload

    def store(self, payload: dict[str, Any]) -> None:
        self._payload = payload
        self._stamped_at = time.monotonic()

    def drop(self) -> None:
        self._payload = None

    @property
    def lock(self) -> asyncio.Lock:
        return self._lock


class BarCache:
    def __init__(self, ttl_seconds: int, entries_max: int) -> None:
        self._ttl = ttl_seconds
        self._entries_max = entries_max
        self._entries: OrderedDict[str, tuple[float, list[dict[str, Any]]]] = OrderedDict()
        self._lock = asyncio.Lock()

    def fresh(self, key: str) -> list[dict[str, Any]] | None:
        entry = self._entries.get(key)
        if entry is None or time.monotonic() - entry[0] > self._ttl:
            return None
        self._entries.move_to_end(key)
        return entry[1]

    def store(self, key: str, bars: list[dict[str, Any]]) -> None:
        self._entries[key] = (time.monotonic(), bars)
        self._entries.move_to_end(key)
        while len(self._entries) > self._entries_max:
            self._entries.popitem(last=False)

    @property
    def lock(self) -> asyncio.Lock:
        return self._lock


class RuntimeStore:
    def __init__(self) -> None:
        self._snapshot: RuntimeSnapshot | None = None

    def publish(self, snapshot: RuntimeSnapshot) -> bool:
        current = self._snapshot
        if current is not None:
            if snapshot.run_id == current.run_id and snapshot.sequence <= current.sequence:
                return False
            if snapshot.run_id != current.run_id and snapshot.started_at <= current.started_at:
                return False
        self._snapshot = snapshot
        return True

    def read(self) -> RuntimeSnapshot | None:
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
RUNTIME_BODY_BYTES_MAX = 65_536
RUNTIME_SIGNATURE_ENVELOPE_BYTES = 51
RUNTIME_REQUEST_BYTES_MAX = RUNTIME_BODY_BYTES_MAX + RUNTIME_SIGNATURE_ENVELOPE_BYTES
CHART_TIMEFRAMES: dict[str, dict[str, Any]] = {
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


def session_hour_bars(bars: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not bars:
        return []
    frame = _bar_frame(bars)
    regular = regular_session(frame)
    if regular.empty:
        return []
    index = cast(Any, cast(DatetimeIndex, regular.index))
    starts = session_starts(cast(DatetimeIndex, regular.index))
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
    pad = timedelta(days=int(rules["pad_days"]))
    display = opened - pad
    end = closed + pad
    if (end - display).days > int(rules["span_max"]):
        display = end - timedelta(days=int(rules["span_max"]))
    data = display - timedelta(days=int(rules["warmup_days"]))
    return (
        datetime.combine(data, dtime(0, 0), TRADING_ZONE),
        datetime.combine(display, dtime(0, 0), TRADING_ZONE),
        datetime.combine(end, dtime(23, 59), TRADING_ZONE),
    )


def bars_atr(bars: list[dict[str, Any]]) -> float | None:
    if len(bars) <= PERIOD:
        return None
    frame = _bar_frame(bars).rename(columns={"h": "high", "l": "low", "c": "close"})
    return latest_atr(frame)


def opening_range(
    bars: list[dict[str, Any]], opens: datetime, minutes: int
) -> tuple[float, float] | None:
    closes = opens + timedelta(minutes=minutes)
    inside = [bar for bar in bars if opens <= _bar_time(bar) < closes]
    if not inside:
        return None
    return max(float(bar["h"]) for bar in inside), min(float(bar["l"]) for bar in inside)


def orb_levels(
    strategy: str, direction: int, entry: float, high: float, low: float
) -> dict[str, Any]:
    stop = range_stop(cast(Direction, direction), high, low)
    risk = abs(entry - stop)
    multiples = ORB_TARGET_MULTIPLES[cast(Any, strategy)]
    targets = [entry + direction * risk * multiple for multiple in multiples]
    return {
        "range": {"high": round(high, 4), "low": round(low, 4)},
        "stop": round(stop, 4),
        "targets": [round(value, 4) for value in targets],
    }


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
    snapshot: RuntimeSnapshot | None,
    stale: bool,
) -> dict[str, Any]:
    account, positions, fills, orders, daily, intraday, clock = await asyncio.gather(
        alpaca.account(),
        alpaca.raw_positions(),
        alpaca.raw_fills(),
        alpaca.raw_closed_orders(),
        alpaca.equity("1A", "1D"),
        alpaca.equity("1D", "5Min"),
        alpaca.clock(),
    )

    cycles, open_cycles = match_cycles(fills, orders)
    equity_daily = _equity_series(daily)
    intraday_points, intraday_date = _intraday_series(intraday)

    invested = equity_daily[0]["equity"] if equity_daily else float(account["equity"])
    funded = equity_daily[0]["date"] if equity_daily else ""
    equity = round(float(account["equity"]), 2)
    closes = {row["date"]: float(row["equity"]) for row in equity_daily}

    today = datetime.now(TRADING_ZONE).date().isoformat()
    if not equity_daily or equity_daily[-1]["date"] != today:
        equity_daily.append({"date": today, "equity": equity})

    rows = _position_rows(positions, equity, open_cycles)
    configuration = snapshot.configuration if snapshot else fallback_configuration
    benchmark_start = funded or today

    try:
        bars = await market.daily_bars(BENCHMARK_SYMBOL, benchmark_start)
    except httpx.HTTPError:
        bars = []

    return {
        "asOf": datetime.now(TRADING_ZONE).strftime("%a %-d %b %Y, %H:%M:%S ET"),
        "today": today,
        "accountNumber": str(account["account_number"]),
        "status": str(account["status"]),
        "marketOpen": bool(clock["is_open"]),
        "nextOpen": datetime.fromisoformat(str(clock["next_open"])).strftime("%H:%M ET"),
        "invested": invested,
        "funded": datetime.fromisoformat(funded).strftime("%-d %b %Y") if funded else "—",
        "equity": equity,
        "lastEquity": round(float(account["last_equity"]), 2),
        "cash": round(float(account["cash"]), 2),
        "buyingPower": round(float(account["buying_power"]), 2),
        "marketValue": round(sum(float(row["value"]) for row in rows), 2),
        "unrealised": round(sum(float(row["unreal"]) for row in rows), 2),
        "positionCapPct": round(
            100
            * min(
                POSITION_FRACTION_CAP_MAX,
                configuration.position_fraction_max,
            ),
            2,
        ),
        "dailyLossLimitPct": round(100 * configuration.risk_per_day_max, 2),
        "bot": bot_state(snapshot, stale),
        "strategies": strategy_labels(),
        "windows": entry_windows(),
        "positions": rows,
        "trades": cycles,
        "days": sessions(cycles, closes, invested),
        "totals": totals(cycles),
        "equityDaily": equity_daily,
        "intraday": intraday_points,
        "intradayDate": intraday_date,
        "spy": [{"date": str(bar["t"])[:10], "close": float(bar["c"])} for bar in bars],
    }


async def build_pulse(alpaca: AlpacaReadClient) -> dict[str, Any]:
    account, positions = await asyncio.gather(alpaca.account(), alpaca.raw_positions())
    equity = round(float(account["equity"]), 2)
    marks = _position_marks(positions, equity)
    return {
        "asOf": datetime.now(TRADING_ZONE).strftime("%a %-d %b %Y, %H:%M:%S ET"),
        "equity": equity,
        "cash": round(float(account["cash"]), 2),
        "buyingPower": round(float(account["buying_power"]), 2),
        "marketValue": round(sum(float(mark["value"]) for mark in marks), 2),
        "unrealised": round(sum(float(mark["unreal"]) for mark in marks), 2),
        "positions": marks,
    }


def bot_state(snapshot: RuntimeSnapshot | None, stale: bool) -> dict[str, Any]:
    running = snapshot is not None and snapshot.status == "running" and not stale
    return {
        "status": snapshot.status if snapshot else "unknown",
        "stale": stale,
        "running": running,
        "reported": snapshot is not None,
        "strategies": [strategy_id(name) for name in snapshot.strategies] if snapshot else [],
        "paused": [strategy_id(name) for name in snapshot.paused] if snapshot else [],
        "events": list(reversed(snapshot.events)) if snapshot else [],
    }


def create_dashboard_router(configuration: WebSettings, runtime_store: RuntimeStore) -> APIRouter:
    router = APIRouter()
    mode = b"PAPER" if configuration.alpaca_is_paper else b"LIVE"
    dashboard_html = DASHBOARD_HTML.replace(b"{{ ALPACA_MODE }}", mode)
    for plain, fingerprinted in ASSET_REWRITES.items():
        dashboard_html = dashboard_html.replace(plain, fingerprinted)
    signer = TimestampSigner(
        configuration.state_export_secret.get_secret_value(),
        salt=STATE_SIGNATURE_SALT,
        digest_method=hashlib.sha256,
    )

    ledger_cache = ReadCache(LEDGER_TTL_SECONDS)
    pulse_cache = ReadCache(PULSE_TTL_SECONDS)
    bar_cache = BarCache(CHART_TTL_SECONDS, CHART_CACHE_MAX)

    def alpaca(request: Request) -> AlpacaReadClient:
        return request.state.alpaca

    def market(request: Request) -> AlpacaMarketDataClient:
        return request.state.market

    def runtime_state() -> tuple[RuntimeSnapshot | None, bool]:
        snapshot = runtime_store.read()
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
                        cached = await market(request).bars(
                            symbol,
                            str(CHART_TIMEFRAMES[timeframe]["bar"]),
                            start.isoformat(),
                            end.isoformat(),
                        )
                    bar_cache.store(key, cached)
        return read_response(
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "displayFrom": display.isoformat(),
                "smaLengths": list(SMA_LENGTHS),
                "bars": [
                    {
                        "t": str(bar["t"]),
                        "o": float(bar["o"]),
                        "h": float(bar["h"]),
                        "l": float(bar["l"]),
                        "c": float(bar["c"]),
                        "v": float(bar.get("v") or 0),
                    }
                    for bar in cached
                ],
            },
            60,
        )

    @router.get("/api/levels")
    async def levels(
        request: Request,
        symbol: Annotated[str, Query(min_length=1, max_length=12, pattern=r"^[A-Z][A-Z.]*$")],
        strategy: Annotated[
            Literal["orb", "orb_momentum", "sma", "tfb_50", "unattributed"], Query()
        ],
        side: Annotated[Literal["long", "short"], Query()],
        entry: Annotated[float, Query(gt=0)],
        opened: Annotated[str, Query(pattern=r"^\d{4}-\d{2}-\d{2}$")],
    ) -> JSONResponse:
        try:
            opened_on = parse_day(opened)
        except ValueError:
            return error_response("The open date is invalid", 422)

        key = f"levels|{symbol}|{strategy}|{side}|{entry}|{opened}"
        cached = bar_cache.fresh(key)
        if cached is not None:
            return read_response(cached[0] if cached else {}, 300)

        direction = 1 if side == "long" else -1
        payload: dict[str, Any] = {"strategy": strategy, "reconstructed": True}
        bounds = session_bounds(opened_on)

        async with bar_cache.lock:
            if strategy in ORB_OPENING_MINUTES and bounds is not None:
                opens = bounds[0]
                minutes = ORB_OPENING_MINUTES[cast(Any, strategy)]
                session = await market(request).bars(
                    symbol,
                    "5Min",
                    opens.isoformat(),
                    (opens + timedelta(minutes=3 * minutes)).isoformat(),
                    limit=10,
                )
                found = opening_range(session, opens, minutes)
                if found is not None:
                    payload.update(orb_levels(strategy, direction, entry, *found))
            elif strategy in DAILY_STOP_ATR_MULTIPLES:
                history = await market(request).bars(
                    symbol,
                    "1Day",
                    (opened_on - timedelta(days=LEVELS_HISTORY_DAYS)).isoformat(),
                    datetime.combine(opened_on, dtime(0, 0), TRADING_ZONE).isoformat(),
                    limit=LEVELS_HISTORY_DAYS,
                )
                average_range = bars_atr(history)
                if average_range is not None:
                    distance = DAILY_STOP_ATR_MULTIPLES[cast(Any, strategy)] * average_range
                    payload["stop"] = round(entry - direction * distance, 4)
                    payload["atr"] = round(average_range, 4)
            bar_cache.store(key, [payload])
        return read_response(payload, 300)

    @router.get("/api/strategies")
    async def strategies() -> JSONResponse:
        snapshot, _ = runtime_state()
        reported = snapshot is not None
        active_configuration = (
            snapshot.configuration if snapshot else configuration.trading_configuration
        )
        return read_response(strategy_spec(active_configuration, configured=reported), 60)

    @router.get("/api/ledger")
    async def ledger(request: Request) -> JSONResponse:
        snapshot, stale = runtime_state()
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
            mark["symbol"] for mark in cached["positions"]
        }:
            ledger_cache.drop()

        return read_response(cached, 0)

    @router.post("/internal/state", status_code=204)
    async def publish_runtime(request: Request) -> Response:
        chunks: list[bytes] = []
        size = 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > RUNTIME_REQUEST_BYTES_MAX:
                return error_response("Runtime snapshot is too large", 413)
            chunks.append(chunk)
        try:
            body, signed_at = signer.unsign(
                b"".join(chunks),
                max_age=SIGNATURE_WINDOW_SECONDS,
                return_timestamp=True,
            )
        except SignatureExpired:
            return error_response("Runtime signature has expired", 401)
        except BadSignature:
            return error_response("Runtime signature is invalid", 401)
        if len(body) > RUNTIME_BODY_BYTES_MAX:
            return error_response("Runtime snapshot is too large", 413)
        try:
            snapshot = RuntimeSnapshot.model_validate_json(body)
        except ValidationError:
            return error_response("Runtime snapshot is invalid", 422)
        drift = abs((snapshot.heartbeat_at - signed_at).total_seconds())
        if snapshot.started_at > snapshot.heartbeat_at or drift > SIGNATURE_WINDOW_SECONDS:
            return error_response("Runtime snapshot is invalid", 422)
        if not runtime_store.publish(snapshot):
            return error_response("Runtime snapshot is not new", 409)
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


def _bar_time(bar: dict[str, Any]) -> datetime:
    return datetime.fromisoformat(str(bar["t"]).replace("Z", "+00:00")).astimezone(TRADING_ZONE)


def _bar_frame(bars: list[dict[str, Any]]) -> DataFrame:
    frame = DataFrame(
        {
            "o": [float(bar["o"]) for bar in bars],
            "h": [float(bar["h"]) for bar in bars],
            "l": [float(bar["l"]) for bar in bars],
            "c": [float(bar["c"]) for bar in bars],
            "v": [float(bar.get("v") or 0) for bar in bars],
        },
        index=DatetimeIndex([_bar_time(bar) for bar in bars], tz=TRADING_ZONE),
    )
    return frame.sort_index()


def _funded_points(history: dict[str, Any]) -> list[tuple[datetime, float]]:
    return [
        (datetime.fromtimestamp(int(point["timestamp"]), TRADING_ZONE), float(point["equity"]))
        for point in history["points"]
        if point["equity"]
    ]


def _equity_series(history: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"date": when.date().isoformat(), "equity": round(value, 2)}
        for when, value in _funded_points(history)
    ]


def _intraday_series(history: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    points = _funded_points(history)
    rows = [{"t": when.strftime("%H:%M"), "equity": round(value, 2)} for when, value in points]
    return rows, points[0][0].date().isoformat() if points else ""


def _position_marks(raw: list[dict[str, Any]], equity: float) -> list[dict[str, Any]]:
    marks: list[dict[str, Any]] = []
    for item in raw:
        value = float(item["market_value"])
        marks.append(
            {
                "symbol": str(item["symbol"]),
                "side": "long" if item["side"] == "long" else "short",
                "qty": round(abs(float(item["qty"])), 4),
                "entry": round(float(item["avg_entry_price"]), 4),
                "last": round(float(item["current_price"]), 4),
                "value": round(value, 2),
                "unreal": round(float(item["unrealized_pl"]), 2),
                "unrealPct": round(float(item["unrealized_plpc"]) * 100, 2),
                "weight": round(value / equity * 100, 2) if equity else 0.0,
            }
        )
    marks.sort(key=lambda mark: -float(mark["value"]))
    return marks


def _position_rows(
    raw: list[dict[str, Any]],
    equity: float,
    open_cycles: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for mark in _position_marks(raw, equity):
        held = open_cycles.get(mark["symbol"], {})
        rows.append(
            {
                **mark,
                "strategy": held.get("strategy", "unattributed"),
                "opened": held.get("opened", "—"),
                "inDate": held.get("inDate"),
                "inMinute": held.get("inMinute"),
                "fills": held.get("fills", []),
            }
        )
    return rows
