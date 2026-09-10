import asyncio
import hashlib
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from datetime import time as dtime
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from itsdangerous import BadSignature, SignatureExpired, TimestampSigner
from pydantic import ValidationError
from starlette.responses import FileResponse

from mt.config.settings import WebSettings, settings
from mt.config.values import ChartTimeframe, StrategyKey, Symbol, is_strategy_key
from mt.data.alpaca import AccountObservation, BarsClientAlpaca, TradingClientAlpaca
from mt.exchange import TRADING_ZONE, session_bounds
from mt.position import Direction
from mt.snapshot import STATE_SIGNATURE_SALT, StateSnapshot
from mt.strategies.breakout import Breakout
from mt.strategies.daily import Daily
from mt.strategies.order_tag import Unattributed
from mt.strategies.registry import strategy_class

from .bars import bar_averages, bars_atr, chart_window, session_hour_bars
from .cache import Cache
from .ledger import Ledger, build_ledger, match_trades
from .levels import Levels, add_breakout_levels, opening_range
from .pulse import bot_state, build_pulse
from .state import StateStore
from .strategies import entry_windows, strategy_config


ASSET_DIRECTORY = Path(__file__).with_name("assets")
ASSET_PATHS = sorted(
    path for path in ASSET_DIRECTORY.iterdir() if path.is_file() and path.name != "dashboard.html"
)
ASSET_FINGERPRINTS = {
    path: f"{path.stem}.{hashlib.sha256(path.read_bytes()).hexdigest()[:12]}{path.suffix}"
    for path in ASSET_PATHS
}
ASSET_ROUTES = {served: path for path, served in ASSET_FINGERPRINTS.items()} | {
    path.name: path for path in ASSET_PATHS
}
ASSET_REWRITES = {
    f"/assets/{path.name}".encode(): f"/assets/{served}".encode()
    for path, served in ASSET_FINGERPRINTS.items()
    if path.suffix != ".woff2"
}
DASHBOARD_HTML = (ASSET_DIRECTORY / "dashboard.html").read_bytes()
NO_STORE = {"Cache-Control": "no-store"}
IMMUTABLE = {"Cache-Control": "public, max-age=31536000, immutable"}
DASHBOARD_HEADERS = {
    "Cache-Control": "private, no-cache",
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; "
        "style-src 'self'; font-src 'self'; "
        "connect-src 'self'; img-src 'self' data:; "
        "object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
    ),
}
LEDGER_KEY = "ledger"


def error_response(
    detail: str, status_code: int, headers: dict[str, str] | None = None
) -> JSONResponse:
    return JSONResponse(
        {"detail": detail}, status_code=status_code, headers={**NO_STORE, **(headers or {})}
    )


def read_response(
    data: Any, max_age: int, read_at: datetime | None = None, **metadata: Any
) -> JSONResponse:
    content = {"data": data, "read_at": read_at or datetime.now(UTC), **metadata}
    return JSONResponse(
        jsonable_encoder(content),
        headers={"Cache-Control": f"private, max-age={max_age}, must-revalidate", "Vary": "Cookie"},
    )


def dashboard_router(configuration: WebSettings, state_store: StateStore) -> APIRouter:
    @asynccontextmanager
    async def lifespan(_: Any) -> AsyncGenerator[None]:
        try:
            yield
        finally:
            await asyncio.gather(*(cache.close() for cache in caches))

    router = APIRouter(lifespan=lifespan)
    mode = settings.broker.mode.upper().encode()
    dashboard_html = DASHBOARD_HTML.replace(b"{{ BROKER_MODE }}", mode)
    for plain, fingerprinted in ASSET_REWRITES.items():
        dashboard_html = dashboard_html.replace(plain, fingerprinted)
    signer = TimestampSigner(
        settings.export.secret.get_secret_value(),
        salt=STATE_SIGNATURE_SALT,
        digest_method=hashlib.sha256,
    )

    dashboard_section = configuration.dashboard
    heartbeat_timeout = timedelta(seconds=configuration.web.heartbeat_timeout_seconds)
    signature_window_seconds = configuration.web.signature_window_seconds
    state_body_bytes_max = configuration.web.state_body_bytes_max
    state_request_bytes_max = state_body_bytes_max + len(signer.sign(b""))

    ledger_cache = Cache[tuple[datetime, Ledger]](dashboard_section.ledger_ttl_seconds)
    account_cache = Cache[AccountObservation](dashboard_section.pulse_ttl_seconds)
    match_history = lru_cache(maxsize=dashboard_section.history_cache_max)(match_trades)
    benchmark_symbol = settings.benchmark_symbol
    chart_ttl = dashboard_section.chart_ttl_seconds
    chart_cache_max = dashboard_section.chart_cache_max
    bar_cache = Cache[tuple[datetime, dict[str, Any]]](chart_ttl, chart_cache_max)
    levels_cache = Cache[Levels](chart_ttl, chart_cache_max)
    caches = (ledger_cache, account_cache, bar_cache, levels_cache)

    def trading(request: Request) -> TradingClientAlpaca:
        return request.state.trading

    async def observation(request: Request) -> AccountObservation:
        return await account_cache.get_or_build(LEDGER_KEY, trading(request).observation)

    def bars_client(request: Request) -> BarsClientAlpaca:
        return request.state.bars

    def read_state() -> tuple[StateSnapshot | None, bool]:
        snapshot = state_store.read()
        stale = snapshot is None or datetime.now(UTC) - snapshot.heartbeat_at > heartbeat_timeout
        return snapshot, stale

    @router.get("/")
    async def dashboard() -> Response:
        return Response(dashboard_html, media_type="text/html", headers=DASHBOARD_HEADERS)

    @router.get("/assets/{filename}")
    async def asset(filename: str) -> Response:
        path = ASSET_ROUTES.get(filename)
        if path is None:
            return error_response("Asset was not found", 404)
        return FileResponse(
            path, headers=IMMUTABLE if filename in ASSET_FINGERPRINTS.values() else NO_STORE
        )

    @router.get("/api/session")
    async def session(request: Request) -> JSONResponse:
        token = request.session.get("csrf_token")
        if not isinstance(token, str):
            return error_response("Session is invalid", 401)
        return JSONResponse(
            {
                "csrf_token": token,
                "refresh_seconds": dashboard_section.refresh_poll_seconds,
                "pulse_seconds": dashboard_section.pulse_poll_seconds,
                "sma_colors": dashboard_section.sma_colors,
            },
            headers=NO_STORE,
        )

    @router.get("/api/bars")
    async def bars(
        request: Request,
        symbol: Annotated[Symbol, Query()],
        timeframe: Annotated[ChartTimeframe, Query()],
        opened: Annotated[str, Query(pattern=r"^\d{4}-\d{2}-\d{2}$")],
        closed: Annotated[str, Query(pattern=r"^\d{4}-\d{2}-\d{2}$")],
    ) -> JSONResponse:
        try:
            opened_at = date.fromisoformat(opened)
            closed_at = date.fromisoformat(closed)
        except ValueError:
            return error_response("The dates are invalid", 422)
        if closed_at < opened_at:
            return error_response("The close cannot precede the open", 422)

        rules = dashboard_section.chart_timeframes[timeframe]
        start, display, end = chart_window(rules, opened_at, closed_at)

        async def build() -> tuple[datetime, dict[str, Any]]:
            if timeframe == "1Hour":
                half = await bars_client(request).bars(
                    symbol,
                    dashboard_section.session_source,
                    start.isoformat(),
                    end.isoformat(),
                    limit=dashboard_section.session_source_bars_max,
                    pages_max=dashboard_section.session_source_pages_max,
                )
                rows = session_hour_bars(half)
            else:
                rows = await bars_client(request).bars(
                    symbol, timeframe, start.isoformat(), end.isoformat()
                )
            read_at = datetime.now(UTC)
            return read_at, {
                "symbol": symbol,
                "timeframe": timeframe,
                "displayFrom": display.isoformat(),
                "averages": bar_averages(rows, dashboard_section.sma_lengths),
                "bars": rows,
            }

        key = repr((symbol, timeframe, start, display, end, settings.bars, dashboard_section))
        read_at, payload = await bar_cache.get_or_build(key, build)
        return read_response(payload, dashboard_section.chart_max_age_seconds, read_at)

    @router.get("/api/levels")
    async def levels(
        request: Request,
        symbol: Annotated[Symbol, Query()],
        strategy_key: Annotated[StrategyKey | Unattributed, Query()],
        side: Annotated[Literal["long", "short"], Query()],
        entry: Annotated[float, Query(gt=0)],
        opened: Annotated[str, Query(pattern=r"^\d{4}-\d{2}-\d{2}$")],
    ) -> JSONResponse:
        try:
            opened_at = date.fromisoformat(opened)
        except ValueError:
            return error_response("The open date is invalid", 422)

        async def build() -> Levels:
            direction: Direction = 1 if side == "long" else -1
            payload = Levels(strategy_key=strategy_key)
            bounds = session_bounds(opened_at)
            found_class = strategy_class(strategy_key) if is_strategy_key(strategy_key) else None
            if found_class is not None and issubclass(found_class, Breakout) and bounds:
                opens = bounds[0]
                minutes = found_class.opening_minutes
                span = dashboard_section.levels_range_multiple * minutes
                opening_bars = await bars_client(request).bars(
                    symbol,
                    dashboard_section.levels_source,
                    opens.isoformat(),
                    (opens + timedelta(minutes=span)).isoformat(),
                    limit=dashboard_section.levels_source_bars_max,
                )
                found = opening_range(opening_bars, opens, minutes)
                if found is not None:
                    add_breakout_levels(payload, found_class, direction, entry, *found)
            elif found_class is not None and issubclass(found_class, Daily):
                historical_bars = await bars_client(request).bars(
                    symbol,
                    "1Day",
                    (
                        opened_at - timedelta(days=dashboard_section.levels_lookback_days)
                    ).isoformat(),
                    datetime.combine(opened_at, dtime(0, 0), TRADING_ZONE).isoformat(),
                    limit=dashboard_section.levels_lookback_days,
                )
                average_range = bars_atr(historical_bars)
                if average_range is not None:
                    distance = found_class.stop_atr_multiple * average_range
                    payload["stop"] = round(entry - direction * distance, 4)
                    payload["atr"] = round(average_range, 4)
            return payload

        key = f"levels|{symbol}|{strategy_key}|{side}|{entry}|{opened}"
        payload = await levels_cache.get_or_build(key, build)
        return read_response(payload, dashboard_section.levels_max_age_seconds)

    @router.get("/api/strategies")
    async def strategies() -> JSONResponse:
        snapshot, _ = read_state()
        reported = snapshot is not None
        active_configuration = snapshot.configuration if snapshot else settings
        return read_response(
            strategy_config(active_configuration, configured=reported),
            dashboard_section.strategies_max_age_seconds,
        )

    @router.get("/api/ledger")
    async def ledger(request: Request) -> JSONResponse:
        snapshot, stale = read_state()

        async def build() -> tuple[datetime, Ledger]:
            account = await observation(request)
            result = await build_ledger(
                account,
                trading(request),
                bars_client(request),
                benchmark_symbol,
                dashboard_section,
                match_history,
            )
            return account.read_at, result

        read_at, cached = await ledger_cache.get_or_build(LEDGER_KEY, build)
        reported_configuration = snapshot.configuration if snapshot else settings
        risk = reported_configuration.risk
        return read_response(
            {
                **cached,
                "bot": bot_state(snapshot, stale),
                "windows": entry_windows(reported_configuration),
                "positionCapPct": round(100 * risk.position_fraction_max, 2),
                "dailyLossLimitPct": round(100 * risk.per_day_max, 2),
            },
            dashboard_section.ledger_max_age_seconds,
            read_at,
        )

    @router.get("/api/pulse")
    async def pulse(request: Request) -> JSONResponse:
        account = await observation(request)
        cached = build_pulse(account)
        held = ledger_cache.fresh(LEDGER_KEY)
        if held is not None and {row.symbol for row in held[1]["positions"]} != {
            row.symbol for row in cached["positions"]
        }:
            ledger_cache.drop(LEDGER_KEY)
        return read_response(cached, 0, account.read_at)

    @router.post("/internal/state", status_code=204)
    async def publish_state(request: Request) -> Response:
        chunks: list[bytes] = []
        size = 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > state_request_bytes_max:
                return error_response("State snapshot is too large", 413)
            chunks.append(chunk)
        try:
            body, signed_at = signer.unsign(
                b"".join(chunks),
                max_age=signature_window_seconds,
                return_timestamp=True,
            )
        except SignatureExpired:
            return error_response("State signature has expired", 401)
        except BadSignature:
            return error_response("State signature is invalid", 401)
        if len(body) > state_body_bytes_max:
            return error_response("State snapshot is too large", 413)
        try:
            snapshot = StateSnapshot.model_validate_json(body)
            if len(snapshot.events) > settings.export.events_max:
                return error_response("State snapshot has too many events", 422)
        except ValidationError:
            return error_response("State snapshot is invalid", 422)
        drift = abs((snapshot.heartbeat_at - signed_at).total_seconds())
        if snapshot.started_at > snapshot.heartbeat_at or drift > signature_window_seconds:
            return error_response("State snapshot is invalid", 422)
        if not state_store.publish(snapshot):
            return error_response("State snapshot is not new", 409)
        return Response(status_code=204, headers=NO_STORE)

    return router
