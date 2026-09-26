import asyncio
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
from starlette.staticfiles import StaticFiles

from mt.data.alpaca import AccountRead, TradingClientAlpaca
from mt.data.asset import Asset, AssetType
from mt.data.bars import BarsClientAlpaca, check_supported_asset
from mt.exchange import TRADING_ZONE, session_bounds
from mt.rules.settings import WebSettings
from mt.rules.shared import settings
from mt.rules.values import ChartTimeframe, StrategyKey, Symbol, Unattributed, is_strategy_key
from mt.sizing import Direction
from mt.state import read_state
from mt.strategies.breakout import Breakout
from mt.strategies.daily import Daily
from mt.strategies.registry import STRATEGIES_BY_KEY

from .bars import bar_averages, bars_atr, chart_window, session_bars, session_hour_bars
from .cache import Cache
from .ledger import Ledger, build_ledger, match_trades
from .levels import Levels, add_breakout_levels, opening_range
from .snapshot import bot_state, build_snapshot
from .strategies import entry_windows, strategy_rules


ASSET_DIRECTORY = Path(__file__).with_name("assets")
DASHBOARD_HTML = Path(__file__).with_name("dashboard.html").read_bytes()
NO_STORE = {"Cache-Control": "no-store"}
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


def dashboard_router(configuration: WebSettings) -> APIRouter:
    @asynccontextmanager
    async def lifespan(_: Any) -> AsyncGenerator[None]:
        try:
            yield
        finally:
            await asyncio.gather(*(cache.close() for cache in caches))

    router = APIRouter(lifespan=lifespan)
    mode = settings.broker.mode.upper().encode()
    dashboard_html = DASHBOARD_HTML.replace(b"{{ BROKER_MODE }}", mode)
    router.mount("/assets", StaticFiles(directory=ASSET_DIRECTORY), name="assets")
    dashboard_section = configuration.dashboard
    heartbeat_timeout = timedelta(seconds=configuration.web.heartbeat_timeout_seconds)

    ledger_cache = Cache[tuple[datetime, Ledger]](dashboard_section.ledger_ttl_seconds)
    account_cache = Cache[AccountRead](dashboard_section.snapshot_ttl_seconds)
    match_history = lru_cache(maxsize=dashboard_section.history_cache_max)(match_trades)
    chart_ttl = dashboard_section.chart_ttl_seconds
    chart_cache_max = dashboard_section.chart_cache_max
    bar_cache = Cache[tuple[datetime, dict[str, Any]]](chart_ttl, chart_cache_max)
    levels_cache = Cache[tuple[datetime, Levels]](chart_ttl, chart_cache_max)
    name_cache = Cache[str](dashboard_section.name_ttl_seconds, dashboard_section.name_cache_max)
    caches = (ledger_cache, account_cache, bar_cache, levels_cache, name_cache)

    def trading(request: Request) -> TradingClientAlpaca:
        return request.state.trading

    async def account_read(request: Request) -> AccountRead:
        return await account_cache.get_or_build(LEDGER_KEY, trading(request).read)

    def bars_client(request: Request) -> BarsClientAlpaca:
        return request.state.bars

    async def asset_name(request: Request, symbol: Symbol) -> str:
        return await name_cache.get_or_build(symbol, lambda: trading(request).asset_name(symbol))

    @router.get("/")
    async def dashboard() -> Response:
        return Response(dashboard_html, media_type="text/html", headers=DASHBOARD_HEADERS)

    @router.get("/api/session")
    async def session(request: Request) -> JSONResponse:
        token = request.session.get("csrf_token")
        if not isinstance(token, str):
            return error_response("Login is invalid", 401)
        return JSONResponse(
            {
                "csrf_token": token,
                "refresh_seconds": dashboard_section.refresh_poll_seconds,
                "snapshot_seconds": dashboard_section.snapshot_poll_seconds,
                "sma_colors": dashboard_section.sma_colors,
            },
            headers=NO_STORE,
        )

    @router.get("/api/bars")
    async def bars(
        request: Request,
        symbol: Annotated[Symbol, Query()],
        timeframe: Annotated[ChartTimeframe, Query()],
        opened: Annotated[date, Query()],
        closed: Annotated[date, Query()],
    ) -> JSONResponse:
        try:
            instrument = _query_asset(symbol)
        except ValueError:
            return error_response("The asset is invalid", 422)
        if closed < opened:
            return error_response("The close cannot precede the open", 422)

        spans = dashboard_section.chart_timeframes[timeframe]
        start, display, end = chart_window(spans, opened, closed)

        async def build() -> tuple[datetime, dict[str, Any]]:
            if timeframe == "1Hour" and instrument.asset_type == AssetType.STOCK:
                half = await bars_client(request).series(
                    instrument,
                    dashboard_section.session_source,
                    start,
                    end,
                    limit=dashboard_section.session_source_bars_max,
                    pages_max=dashboard_section.session_source_pages_max,
                )
                rows = session_hour_bars(half)
            else:
                rows = await bars_client(request).series(
                    instrument, timeframe, start, end, limit=dashboard_section.bars_max, pages_max=1
                )
                if timeframe == "5Min" and instrument.asset_type == AssetType.STOCK:
                    rows = session_bars(rows)
            read_at = datetime.now(UTC)
            return read_at, {
                "symbol": symbol,
                "name": await asset_name(request, symbol),
                "timeframe": timeframe,
                "displayFrom": display.isoformat(),
                "averages": bar_averages(rows, dashboard_section.sma_lengths),
                "bars": rows,
            }

        key = repr((instrument, timeframe, start, display, end))
        read_at, payload = await bar_cache.get_or_build(key, build)
        return read_response(payload, dashboard_section.chart_max_age_seconds, read_at)

    @router.get("/api/levels")
    async def levels(
        request: Request,
        symbol: Annotated[Symbol, Query()],
        strategy_key: Annotated[StrategyKey | Unattributed, Query()],
        side: Annotated[Literal["long", "short"], Query()],
        entry: Annotated[float, Query(gt=0)],
        opened: Annotated[date, Query()],
    ) -> JSONResponse:
        try:
            instrument = _query_asset(symbol)
        except ValueError:
            return error_response("The asset is invalid", 422)

        async def build() -> tuple[datetime, Levels]:
            direction: Direction = 1 if side == "long" else -1
            payload = Levels(strategy_key=strategy_key)
            if instrument.asset_type != AssetType.STOCK:
                return datetime.now(UTC), payload
            bounds = session_bounds(opened)
            found_class = STRATEGIES_BY_KEY[strategy_key] if is_strategy_key(strategy_key) else None
            if found_class is not None and issubclass(found_class, Breakout) and bounds:
                opens = bounds[0]
                minutes = found_class.opening_minutes
                span = dashboard_section.levels_range_multiple * minutes
                opening_bars = await bars_client(request).series(
                    instrument,
                    dashboard_section.levels_source,
                    opens,
                    opens + timedelta(minutes=span),
                    limit=dashboard_section.levels_source_bars_max,
                    pages_max=1,
                )
                found = opening_range(opening_bars, opens, minutes)
                if found is not None:
                    add_breakout_levels(payload, found_class, direction, entry, *found)
            elif found_class is not None and issubclass(found_class, Daily):
                historical_bars = await bars_client(request).series(
                    instrument,
                    "1Day",
                    datetime.combine(
                        opened - timedelta(days=dashboard_section.levels_lookback_days),
                        dtime(0, 0),
                        TRADING_ZONE,
                    ),
                    datetime.combine(opened, dtime(0, 0), TRADING_ZONE),
                    limit=dashboard_section.levels_lookback_days,
                    pages_max=1,
                )
                average_range = bars_atr(historical_bars)
                if average_range is not None:
                    distance = found_class.stop_atr_multiple * average_range
                    payload["stop"] = round(entry - direction * distance, 4)
                    payload["atr"] = round(average_range, 4)
            return datetime.now(UTC), payload

        key = repr((instrument, strategy_key, side, entry, opened))
        read_at, payload = await levels_cache.get_or_build(key, build)
        return read_response(payload, dashboard_section.levels_max_age_seconds, read_at)

    @router.get("/api/strategies")
    async def strategies(request: Request) -> JSONResponse:
        state = await read_state(request.state.state)
        reported = state is not None
        rules = state.rules if state else settings
        return read_response(
            strategy_rules(rules, reported=reported),
            dashboard_section.strategies_max_age_seconds,
        )

    @router.get("/api/ledger")
    async def ledger(request: Request) -> JSONResponse:
        state = await read_state(request.state.state)

        async def build() -> tuple[datetime, Ledger]:
            account = await account_read(request)
            result = await build_ledger(
                account,
                trading(request),
                bars_client(request),
                settings.benchmark_symbol,
                dashboard_section,
                match_history,
            )
            return account.read_at, result

        read_at, cached = await ledger_cache.get_or_build(LEDGER_KEY, build)
        rules = state.rules if state else settings
        risk = rules.risk
        return read_response(
            {
                **cached,
                "bot": bot_state(state, heartbeat_timeout),
                "windows": entry_windows(rules),
                "positionCapUsd": risk.notional_usd_max,
                "dailyLossLimitPct": round(100 * risk.per_day_max, 2),
            },
            dashboard_section.ledger_max_age_seconds,
            read_at,
        )

    @router.get("/api/snapshot")
    async def snapshot(request: Request) -> JSONResponse:
        account = await account_read(request)
        cached = build_snapshot(account)
        held = ledger_cache.fresh(LEDGER_KEY)
        if held is not None and {row.symbol for row in held[1]["positions"]} != {
            row.symbol for row in cached["positions"]
        }:
            ledger_cache.drop(LEDGER_KEY)
        return read_response(cached, 0, account.read_at)

    return router


def _query_asset(symbol: str) -> Asset:
    asset = Asset.from_symbol(symbol)
    check_supported_asset(asset)
    return asset
