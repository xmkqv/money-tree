import asyncio
import hashlib
import time
from collections import OrderedDict
from datetime import UTC, date, datetime, timedelta
from datetime import time as dtime
from pathlib import Path
from typing import Annotated, Any, Literal

import httpx
from fastapi import APIRouter, Query, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from itsdangerous import BadSignature, SignatureExpired, TimestampSigner
from pydantic import AwareDatetime, ValidationError
from starlette.responses import FileResponse

from bot.types import STATE_SIGNATURE_SALT, RuntimeSnapshot
from ui.alpaca import AlpacaMarketDataClient, AlpacaReadClient
from ui.config import WebSettings
from ui.ledger import (
    TRADING_ZONE,
    match_cycles,
    parse_day,
    sessions,
    strategy_id,
    strategy_labels,
    summarise,
)
from ui.strategies import entry_windows, strategy_spec


ASSET_DIRECTORY = Path(__file__).with_name("assets")
DASHBOARD_HTML = (ASSET_DIRECTORY / "dashboard.html").read_bytes()
ASSET_MEDIA_TYPES = {
    "dashboard.css": "text/css",
    "dashboard.js": "text/javascript",
    "theme.js": "text/javascript",
}
LEDGER_TTL_SECONDS = 60
BENCHMARK_SYMBOL = "SPY"
POSITION_CAP_FALLBACK = 0.10
DAILY_LOSS_FALLBACK = 0.02
NO_STORE = {"Cache-Control": "no-store"}
IMMUTABLE = {"Cache-Control": "public, max-age=31536000, immutable"}


def _fingerprint_assets() -> tuple[dict[str, tuple[Path, str]], dict[bytes, bytes]]:
    """Give every asset a URL that changes whenever its bytes change.

    Assets are served as immutable, so a browser holding one cached will not
    revalidate it for a year. At a fixed path that silently breaks upgrades: a
    returning visitor keeps the old stylesheet and the old script while the
    markup, which does revalidate, arrives new. The page then renders unstyled
    and no figures ever appear, because the stale script is looking for
    elements that no longer exist. Putting a digest of the contents in the path
    means new bytes are always a new URL, and so always a fresh fetch.
    """
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
HEARTBEAT_TIMEOUT = timedelta(seconds=15)
SIGNATURE_WINDOW_SECONDS = 30
RUNTIME_BODY_BYTES_MAX = 65_536
RUNTIME_SIGNATURE_ENVELOPE_BYTES = 51
RUNTIME_REQUEST_BYTES_MAX = RUNTIME_BODY_BYTES_MAX + RUNTIME_SIGNATURE_ENVELOPE_BYTES
PORTFOLIO_TIMEFRAMES = {"1D": "5Min", "1W": "15Min", "1M": "1D", "1A": "1D"}
DASHBOARD_HEADERS = {
    "Cache-Control": "private, no-cache",
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; "
        "style-src 'self' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; "
        "connect-src 'self'; img-src 'self' data:; "
        "object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
    ),
}


class LedgerCache:
    """Fills and orders are paged reads, so the assembled view is held briefly.

    The bot shares this Alpaca key, and Alpaca rate-limits per key, so the cost
    of the dashboard is capped here rather than left to scale with viewers: one
    assembly per minute regardless of how many people are watching. At the page
    ceiling that is roughly 47 requests a minute against a 200 limit.
    """

    def __init__(self, ttl_seconds: int = LEDGER_TTL_SECONDS) -> None:
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

    @property
    def lock(self) -> asyncio.Lock:
        return self._lock


# How much context each timeframe puts around a trade, and the bar size Alpaca
# is asked for. The window is bounded per timeframe so one chart is always one
# upstream page, whatever the trade's span.
CHART_TIMEFRAMES: dict[str, dict[str, Any]] = {
    "5Min": {"bar": "5Min", "pad_days": 1, "span_max": 10, "warmup_days": 5},
    "1Hour": {"bar": "1Hour", "pad_days": 7, "span_max": 90, "warmup_days": 46},
    "1Day": {"bar": "1Day", "pad_days": 120, "span_max": 900, "warmup_days": 300},
}
SMA_LENGTHS = (20, 50, 200)
CHART_TTL_SECONDS = 120
CHART_CACHE_MAX = 64


class BarCache:
    """Keyed by symbol, timeframe and window, so revisiting a trade is free.

    A chart is one upstream read, but the symbol is chosen by whoever is
    clicking, so the volume is not bounded by the page the way the ledger is.
    Holding each answer briefly keeps a browse through the log from turning into
    a read per click against the limit the bot shares.
    """

    def __init__(self, ttl_seconds: int = CHART_TTL_SECONDS) -> None:
        self._ttl = ttl_seconds
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
        while len(self._entries) > CHART_CACHE_MAX:
            self._entries.popitem(last=False)

    @property
    def lock(self) -> asyncio.Lock:
        return self._lock


def chart_window(timeframe: str, opened: date, closed: date) -> tuple[datetime, datetime, datetime]:
    """Data start, display start and end for a trade, in exchange time.

    Padding gives the trade somewhere to sit rather than starting hard on the
    entry, and the span is clamped so a long hold cannot ask for a year of
    five-minute bars. The data reaches further back than the display so a
    200-period average has something to average before the first drawn bar —
    otherwise the longest line would simply be missing from every chart.
    """
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


# Reconstruction of the levels an engine would have set, from the same rules the
# composer uses. It is a reconstruction and the page says so: the live stop
# trails once a target is hit, so where it finally sat is not recoverable from
# market data alone.
ATR_PERIOD = 14
DAILY_STOP_MULTIPLES = {"sma": 1.5, "tfb_50": 2.0}
ORB_OPENING_MINUTES = {"orb": 5, "orb_momentum": 10}
ORB_TARGET_MULTIPLES = (1.5, 2.5, 4.0)
ORB_SPAN_MULTIPLES = (0.5, 1.0, 2.0)
ORB_STOP_FRACTION = {1: 0.75, -1: 0.25}


def wilder_atr(bars: list[dict[str, Any]], period: int = ATR_PERIOD) -> float | None:
    """Average true range, smoothed the way pandas-ta smooths it for the bot.

    Reimplemented here rather than imported so the web service does not pull in
    the whole strategy stack — lumibot, pandas-ta and the exchange calendars —
    to draw one dashed line.
    """
    if len(bars) <= period:
        return None
    ranges: list[float] = []
    for index, bar in enumerate(bars):
        high, low = float(bar["h"]), float(bar["l"])
        if index == 0:
            ranges.append(high - low)
            continue
        close = float(bars[index - 1]["c"])
        ranges.append(max(high - low, abs(high - close), abs(low - close)))
    average = ranges[0]
    for value in ranges[1:]:
        average += (value - average) / period
    return average if average > 0 else None


def opening_range(
    bars: list[dict[str, Any]], day: date, minutes: int
) -> tuple[float, float] | None:
    """High and low of the session's first candle of that length."""
    opens = datetime.combine(day, dtime(9, 30), TRADING_ZONE)
    closes = opens + timedelta(minutes=minutes)
    inside = [
        bar
        for bar in bars
        if opens
        <= datetime.fromisoformat(str(bar["t"]).replace("Z", "+00:00")).astimezone(TRADING_ZONE)
        < closes
    ]
    if not inside:
        return None
    return max(float(b["h"]) for b in inside), min(float(b["l"]) for b in inside)


def orb_levels(
    engine: str, direction: int, entry: float, high: float, low: float
) -> dict[str, Any]:
    """The stop and the three targets the composer would have set on this range."""
    span = high - low
    stop = low + span * ORB_STOP_FRACTION[direction]
    if engine == "orb":
        # the five-minute engine re-cuts its targets from the filled price
        risk = abs(entry - stop)
        targets = [entry + direction * risk * multiple for multiple in ORB_TARGET_MULTIPLES]
    else:
        edge = high if direction == 1 else low
        targets = [edge + direction * span * multiple for multiple in ORB_SPAN_MULTIPLES]
    return {
        "range": {"high": round(high, 4), "low": round(low, 4)},
        "stop": round(stop, 4),
        "targets": [round(value, 4) for value in targets],
    }


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


def _funded_points(history: dict[str, Any]) -> list[tuple[datetime, float]]:
    """Equity readings from the point the account was actually funded."""
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


def _position_rows(
    raw: list[dict[str, Any]],
    equity: float,
    open_cycles: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in raw:
        symbol = str(item["symbol"])
        held = open_cycles.get(symbol, {})
        value = float(item["market_value"])
        rows.append(
            {
                "symbol": symbol,
                "side": "long" if item["side"] == "long" else "short",
                "strategy": held.get("strategy", "unattributed"),
                "opened": held.get("opened", "—"),
                # only present when the position matched a cycle in the fill
                # history; without them the page cannot place an entry on a chart
                "inDate": held.get("inDate"),
                "inMinute": held.get("inMinute"),
                "fills": held.get("fills", []),
                "qty": round(abs(float(item["qty"])), 4),
                "entry": round(float(item["avg_entry_price"]), 4),
                "last": round(float(item["current_price"]), 4),
                "value": round(value, 2),
                "unreal": round(float(item["unrealized_pl"]), 2),
                "unrealPct": round(float(item["unrealized_plpc"]) * 100, 2),
                "weight": round(value / equity * 100, 2) if equity else 0.0,
            }
        )
    rows.sort(key=lambda row: -float(row["value"]))
    return rows


async def build_ledger(
    alpaca: AlpacaReadClient,
    market: AlpacaMarketDataClient,
    snapshot: RuntimeSnapshot | None,
    stale: bool,
) -> dict[str, Any]:
    """One assembled view of the account: state, holdings, closed trades, curves."""
    account, positions, fills, orders, daily, intraday, clock = await asyncio.gather(
        alpaca.account(),
        alpaca.positions(),
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
    configuration = snapshot.configuration if snapshot else None
    benchmark_start = funded or today

    try:
        bars = await market.daily_bars(BENCHMARK_SYMBOL, benchmark_start)
    except httpx.HTTPError:
        bars = []

    return {
        "asOf": datetime.now(TRADING_ZONE).strftime("%a %-d %b %Y, %H:%M ET"),
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
            100 * (configuration.position_fraction_max if configuration else POSITION_CAP_FALLBACK),
            2,
        ),
        "dailyLossLimitPct": round(
            100 * (configuration.risk_per_day_max if configuration else DAILY_LOSS_FALLBACK), 2
        ),
        "bot": bot_state(snapshot, stale),
        "strategies": strategy_labels(),
        "windows": entry_windows(),
        "positions": rows,
        "trades": cycles,
        "days": sessions(cycles, closes, invested),
        "totals": summarise(cycles),
        "equityDaily": equity_daily,
        "intraday": intraday_points,
        "intradayDate": intraday_date,
        "spy": [{"date": str(bar["t"])[:10], "close": float(bar["c"])} for bar in bars],
    }


def bot_state(snapshot: RuntimeSnapshot | None, stale: bool) -> dict[str, Any]:
    """Which engines are running right now, as opposed to merely configured.

    A strategy counts as running only while the bot is reporting a live
    heartbeat: a roster read from a snapshot that stopped arriving describes
    what *was* running. Callers overlay this on the cached payload rather than
    letting it age with it, because the snapshot is held in local memory and so
    costs nothing to re-read, while the rest of the view is paged Alpaca calls.
    """
    running = snapshot is not None and snapshot.status == "running" and not stale
    return {
        "status": snapshot.status if snapshot else "unknown",
        "stale": stale,
        "running": running,
        # Without a snapshot the roster is unknown, which is not the same as
        # every engine being switched off.
        "reported": snapshot is not None,
        "strategies": [strategy_id(name) for name in snapshot.strategies] if snapshot else [],
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

    ledger_cache = LedgerCache()
    bar_cache = BarCache()

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

    @router.get("/api/account")
    async def account(request: Request) -> JSONResponse:
        return read_response(await alpaca(request).account(), 5)

    @router.get("/api/positions")
    async def positions(request: Request) -> JSONResponse:
        return read_response(await alpaca(request).positions(), 5)

    @router.get("/api/orders/open")
    async def open_orders(request: Request) -> JSONResponse:
        return read_response(await alpaca(request).orders("open", 100), 5)

    @router.get("/api/orders")
    async def orders(
        request: Request,
        limit: Annotated[int, Query(ge=1, le=100)] = 100,
        until: AwareDatetime | None = None,
    ) -> JSONResponse:
        max_age = 300 if until is not None else 15
        cursor = until.isoformat() if until is not None else None
        return read_response(await alpaca(request).orders("closed", limit, cursor), max_age)

    @router.get("/api/fills")
    async def fills(
        request: Request,
        limit: Annotated[int, Query(ge=1, le=100)] = 100,
        page_token: Annotated[
            str | None,
            Query(
                min_length=55,
                max_length=55,
                pattern=r"^[0-9]{17}::[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}$",
            ),
        ] = None,
    ) -> JSONResponse:
        max_age = 300 if page_token is not None else 15
        return read_response(await alpaca(request).fills(limit, page_token), max_age)

    @router.get("/api/bars")
    async def bars(
        request: Request,
        symbol: Annotated[str, Query(min_length=1, max_length=12, pattern=r"^[A-Z][A-Z.]*$")],
        timeframe: Annotated[Literal["5Min", "1Hour", "1Day"], Query()],
        opened: Annotated[str, Query(pattern=r"^\d{4}-\d{2}-\d{2}$")],
        closed: Annotated[str, Query(pattern=r"^\d{4}-\d{2}-\d{2}$")],
    ) -> JSONResponse:
        """Bars around one trade. The window is derived here, not sent by the page."""
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
        """Where this engine's rules put the stop and targets for one trade.

        Fetched once per trade rather than per timeframe, so switching bar size
        costs nothing, and cached like the bars because the symbol is chosen by
        whoever is clicking rather than bounded by the page.
        """
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

        async with bar_cache.lock:
            if strategy in ORB_OPENING_MINUTES:
                session = await market(request).bars(
                    symbol,
                    "5Min",
                    datetime.combine(opened_on, dtime(9, 30), TRADING_ZONE).isoformat(),
                    datetime.combine(opened_on, dtime(9, 45), TRADING_ZONE).isoformat(),
                    limit=10,
                )
                found = opening_range(session, opened_on, ORB_OPENING_MINUTES[strategy])
                if found is not None:
                    payload.update(orb_levels(strategy, direction, entry, *found))
            elif strategy in DAILY_STOP_MULTIPLES:
                history = await market(request).bars(
                    symbol,
                    "1Day",
                    (opened_on - timedelta(days=90)).isoformat(),
                    datetime.combine(opened_on, dtime(0, 0), TRADING_ZONE).isoformat(),
                    limit=90,
                )
                average_range = wilder_atr(history)
                if average_range is not None:
                    distance = DAILY_STOP_MULTIPLES[strategy] * average_range
                    payload["stop"] = round(entry - direction * distance, 4)
                    payload["atr"] = round(average_range, 4)
            bar_cache.store(key, [payload])
        return read_response(payload, 300)

    @router.get("/api/strategies")
    async def strategies() -> JSONResponse:
        """The rule sheet, quoting whatever risk limits the bot is reporting."""
        snapshot, _ = runtime_state()
        configuration = snapshot.configuration if snapshot else None
        return read_response(strategy_spec(configuration), 60)

    @router.get("/api/ledger")
    async def ledger(request: Request) -> JSONResponse:
        snapshot, stale = runtime_state()
        cached = ledger_cache.fresh()
        if cached is None:
            async with ledger_cache.lock:
                cached = ledger_cache.fresh()
                if cached is None:
                    cached = await build_ledger(alpaca(request), market(request), snapshot, stale)
                    ledger_cache.store(cached)
        return read_response({**cached, "bot": bot_state(snapshot, stale)}, 10)

    @router.get("/api/equity")
    async def equity(
        request: Request, period: Literal["1D", "1W", "1M", "1A"] = "1D"
    ) -> JSONResponse:
        return read_response(await alpaca(request).equity(period, PORTFOLIO_TIMEFRAMES[period]), 60)

    @router.get("/api/run")
    async def runtime() -> JSONResponse:
        snapshot, stale = runtime_state()
        return read_response(snapshot, 5, stale=stale)

    @router.get("/api/events")
    async def events(limit: Annotated[int, Query(ge=1, le=50)] = 50) -> JSONResponse:
        snapshot, stale = runtime_state()
        data = list(reversed(snapshot.events[-limit:])) if snapshot else []
        return read_response(data, 5, stale=stale)

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
