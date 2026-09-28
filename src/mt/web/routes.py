import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from starlette.staticfiles import StaticFiles

from mt.data.alpaca import AccountRead, EquityPoint, TradingClientAlpaca, upcoming_session_on
from mt.data.asset import Asset, AssetType
from mt.data.bars import BarsClientAlpaca, check_supported_asset
from mt.rules.settings import RuleSettings, WebSettings
from mt.rules.shared import settings
from mt.rules.values import UNATTRIBUTED, ChartTimeframe, StrategyKey, Symbol, Unattributed
from mt.state import State, read_state

from .bars import Chart, bar_averages, chart_window, session_bars, session_hour_bars
from .cache import Cache
from .ledger import Ledger, build_ledger
from .levels import Levels, build_levels
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


@dataclass(frozen=True, slots=True)
class Read[T]:
    data: T
    read_at: datetime


@dataclass(frozen=True, slots=True)
class ReportedRules:
    state: State | None
    rules: RuleSettings
    reported: bool


def error_response(
    detail: str, status_code: int, headers: dict[str, str] | None = None
) -> JSONResponse:
    return JSONResponse(
        {"detail": detail}, status_code=status_code, headers={**NO_STORE, **(headers or {})}
    )


def read_response(read: Read[Any], max_age_seconds: int) -> JSONResponse:
    content = {"data": read.data, "read_at": read.read_at}
    return JSONResponse(
        jsonable_encoder(content),
        headers={
            "Cache-Control": f"private, max-age={max_age_seconds}, must-revalidate",
            "Vary": "Cookie",
        },
    )


def query_asset(symbol: Annotated[Symbol, Query()]) -> Asset:
    try:
        asset = Asset.from_symbol(symbol)
        check_supported_asset(asset)
    except ValueError as error:
        raise HTTPException(422, "The asset is invalid", headers=NO_STORE) from error
    return asset


async def reported_rules(request: Request) -> ReportedRules:
    state = await read_state(request.state.store)
    return ReportedRules(
        state=state, rules=state.rules if state else settings, reported=state is not None
    )


def dashboard_router(configuration: WebSettings) -> APIRouter:
    @asynccontextmanager
    async def lifespan(_: APIRouter) -> AsyncGenerator[None]:
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

    ledger_cache = Cache[str, Read[Ledger]](dashboard_section.ledger_ttl_seconds)
    account_cache = Cache[str, AccountRead](dashboard_section.snapshot_ttl_seconds)
    equity_cache = Cache[date, list[EquityPoint]](dashboard_section.equity_daily_ttl_seconds)
    chart_ttl = dashboard_section.chart_ttl_seconds
    chart_cache_max = dashboard_section.chart_cache_max
    bar_cache = Cache[tuple[Asset, ChartTimeframe, datetime, date, datetime], Read[Chart]](
        chart_ttl, chart_cache_max
    )
    levels_cache = Cache[tuple[Asset, StrategyKey | Unattributed, str, float, date], Read[Levels]](
        chart_ttl, chart_cache_max
    )
    name_cache = Cache[str, str](
        dashboard_section.name_ttl_seconds, dashboard_section.name_cache_max
    )
    caches = (ledger_cache, account_cache, equity_cache, bar_cache, levels_cache, name_cache)

    def trading(request: Request) -> TradingClientAlpaca:
        return request.state.trading

    async def read_account(request: Request) -> AccountRead:
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
        instrument: Annotated[Asset, Depends(query_asset)],
        timeframe: Annotated[ChartTimeframe, Query()],
        opened: Annotated[date, Query()],
        closed: Annotated[date, Query()],
    ) -> JSONResponse:
        if closed < opened:
            return error_response("The close cannot precede the open", 422)

        spans = dashboard_section.chart_timeframes[timeframe]
        start, display, end = chart_window(spans, opened, closed)

        async def build() -> Read[Chart]:
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
            return Read(
                data={
                    "symbol": symbol,
                    "name": await asset_name(request, symbol),
                    "timeframe": timeframe,
                    "displayFrom": display.isoformat(),
                    "averages": bar_averages(rows, dashboard_section.sma_lengths),
                    "bars": rows,
                },
                read_at=datetime.now(UTC),
            )

        key = (instrument, timeframe, start, display, end)
        read = await bar_cache.get_or_build(key, build)
        return read_response(read, dashboard_section.chart_max_age_seconds)

    @router.get("/api/levels")
    async def levels(
        request: Request,
        instrument: Annotated[Asset, Depends(query_asset)],
        strategy_key: Annotated[StrategyKey | Unattributed, Query()],
        side: Annotated[Literal["long", "short"], Query()],
        entry: Annotated[float, Query(gt=0)],
        opened: Annotated[date, Query()],
    ) -> JSONResponse:
        if strategy_key == UNATTRIBUTED or instrument.asset_type != AssetType.STOCK:
            return read_response(
                Read(data=Levels(strategy_key=strategy_key), read_at=datetime.now(UTC)),
                dashboard_section.levels_max_age_seconds,
            )

        async def build() -> Read[Levels]:
            payload = await build_levels(
                bars_client(request),
                dashboard_section,
                instrument,
                strategy_key,
                side,
                entry,
                opened,
            )
            return Read(data=payload, read_at=datetime.now(UTC))

        key = (instrument, strategy_key, side, entry, opened)
        read = await levels_cache.get_or_build(key, build)
        return read_response(read, dashboard_section.levels_max_age_seconds)

    @router.get("/api/strategies")
    async def strategies(
        reported: Annotated[ReportedRules, Depends(reported_rules)],
    ) -> JSONResponse:
        return read_response(
            Read(
                data=strategy_rules(reported.rules, reported=reported.reported),
                read_at=datetime.now(UTC),
            ),
            dashboard_section.strategies_max_age_seconds,
        )

    @router.get("/api/ledger")
    async def ledger(
        request: Request, reported: Annotated[ReportedRules, Depends(reported_rules)]
    ) -> JSONResponse:
        async def build() -> Read[Ledger]:
            account = await read_account(request)
            session_on = upcoming_session_on()
            daily = await equity_cache.get_or_build(
                session_on,
                lambda: trading(request).equity(
                    dashboard_section.equity_daily_period, dashboard_section.equity_daily_timeframe
                ),
            )
            result = await build_ledger(
                account,
                trading(request),
                bars_client(request),
                settings.benchmark_symbol,
                dashboard_section,
                daily,
            )
            return Read(data=result, read_at=account.read_at)

        cached = await ledger_cache.get_or_build(LEDGER_KEY, build)
        risk = reported.rules.risk
        return read_response(
            Read(
                data={
                    **cached.data,
                    "bot": bot_state(reported.state, heartbeat_timeout),
                    "windows": entry_windows(reported.rules),
                    "positionCapUsd": risk.notional_usd_max,
                    "dailyLossLimitPct": round(100 * risk.per_day_max, 2),
                },
                read_at=cached.read_at,
            ),
            dashboard_section.ledger_max_age_seconds,
        )

    @router.get("/api/snapshot")
    async def snapshot(request: Request) -> JSONResponse:
        account = await read_account(request)
        cached = build_snapshot(account)
        held = ledger_cache.fresh(LEDGER_KEY)
        if held is not None and {row.symbol for row in held.data["positions"]} != {
            row.symbol for row in cached["positions"]
        }:
            ledger_cache.drop(LEDGER_KEY)
        return read_response(Read(data=cached, read_at=account.read_at), 0)

    return router
