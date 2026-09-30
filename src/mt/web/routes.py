# pyright: reportUnusedFunction=false
import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any, Literal, TypedDict

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from redis.asyncio import Redis as AsyncRedis
from starlette.staticfiles import StaticFiles

from mt.data.alpaca import AccountRead, EquityPoint, TradingClientAlpaca
from mt.data.asset import Asset, AssetType
from mt.data.bars import BarsClientAlpaca, check_supported_asset
from mt.exchange import today_on, upcoming_session_on
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


class AppState(TypedDict):
    store: AsyncRedis
    trading: TradingClientAlpaca
    bars: BarsClientAlpaca


class AppRequest(Request[AppState]):
    pass


@dataclass(frozen=True, slots=True)
class Read[T]:
    data: T
    read_at: datetime


@dataclass(frozen=True, slots=True)
class ReportedRules:
    state: State | None
    rules: RuleSettings

    @property
    def is_reported(self) -> bool:
        return self.state is not None


ASSET_DIRECTORY = Path(__file__).with_name("assets")
DASHBOARD_HTML = Path(__file__).with_name("dashboard.html").read_bytes()
NO_STORE = {"Cache-Control": "no-store"}
DASHBOARD_HEADERS = {
    "Cache-Control": "private, no-cache",
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; "
        "style-src 'self'; font-src 'self'; "
        "connect-src 'self'; "
        "object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
    ),
}
ACCOUNT_KEY = "account"
LEDGER_KEY = "ledger"


def error_response(
    detail: str, status_code: int, headers: dict[str, str] | None = None
) -> JSONResponse:
    return JSONResponse(
        {"detail": detail}, status_code=status_code, headers={**NO_STORE, **(headers or {})}
    )


def dashboard_router(configuration: WebSettings) -> APIRouter:
    @asynccontextmanager
    async def lifespan(_: APIRouter) -> AsyncGenerator[None]:
        try:
            yield
        finally:
            await asyncio.gather(*(cache.close() for cache in caches))

    router = APIRouter(lifespan=lifespan)
    broker_mode = settings.broker.mode.upper().encode()
    dashboard_html = DASHBOARD_HTML.replace(b"{{ BROKER_MODE }}", broker_mode)
    router.mount("/assets", StaticFiles(directory=ASSET_DIRECTORY), name="assets")
    dashboard_section = configuration.dashboard
    heartbeat_timeout = timedelta(seconds=configuration.web.heartbeat_timeout_seconds)

    ledger_cache = Cache[str, Read[Ledger]](dashboard_section.ledger_ttl_seconds)
    account_cache = Cache[str, AccountRead](dashboard_section.snapshot_ttl_seconds)
    equity_cache = Cache[date, list[EquityPoint]](dashboard_section.equity_daily_ttl_seconds)
    chart_ttl_seconds = dashboard_section.chart_ttl_seconds
    chart_cache_max = dashboard_section.chart_cache_max
    bar_cache = Cache[tuple[Asset, ChartTimeframe, datetime, datetime], Read[Chart]](
        chart_ttl_seconds, chart_cache_max
    )
    levels_cache = Cache[tuple[Asset, StrategyKey, str, float, date], Read[Levels]](
        chart_ttl_seconds, chart_cache_max
    )
    name_cache = Cache[str, str | None](
        dashboard_section.name_ttl_seconds, dashboard_section.name_cache_max
    )
    caches = (ledger_cache, account_cache, equity_cache, bar_cache, levels_cache, name_cache)

    async def read_account(request: AppRequest) -> AccountRead:
        return await account_cache.get_or_build(ACCOUNT_KEY, request.state["trading"].read)

    @router.get("/")
    async def dashboard() -> Response:
        return Response(dashboard_html, media_type="text/html", headers=DASHBOARD_HEADERS)

    @router.get("/api/session")
    async def session(request: Request) -> JSONResponse:
        return JSONResponse(
            {
                "csrf_token": request.session["csrf_token"],
                "refresh_seconds": dashboard_section.refresh_poll_seconds,
                "snapshot_seconds": dashboard_section.snapshot_poll_seconds,
                "stale_seconds": dashboard_section.snapshot_ttl_seconds
                + dashboard_section.snapshot_poll_seconds,
                "sma_colors": dashboard_section.sma_colors,
            },
            headers=NO_STORE,
        )

    @router.get("/api/bars")
    async def bars(
        request: AppRequest,
        instrument: Annotated[Asset, Depends(_query_asset)],
        timeframe: Annotated[ChartTimeframe, Query()],
        opened_on: Annotated[date, Query(alias="opened")],
        closed_on: Annotated[date, Query(alias="closed")],
    ) -> JSONResponse:
        if closed_on < opened_on:
            return error_response("The close cannot precede the open", 422)

        spans = dashboard_section.chart_timeframes[timeframe]
        data_at, display_at, end_at = chart_window(spans, opened_on, closed_on)
        is_stock = instrument.asset_type == AssetType.STOCK

        async def build() -> Read[Chart]:
            read_at = datetime.now(UTC)
            if timeframe == "1Hour" and is_stock:
                half = await request.state["bars"].series(
                    instrument,
                    dashboard_section.session_source,
                    data_at,
                    end_at,
                    limit=dashboard_section.session_source_bars_max,
                    pages_max=dashboard_section.session_source_pages_max,
                )
                rows = session_hour_bars(half)
            else:
                rows = await request.state["bars"].series(
                    instrument,
                    timeframe,
                    data_at,
                    end_at,
                    limit=dashboard_section.bars_max,
                    pages_max=dashboard_section.pages_max,
                )
                if timeframe == "5Min" and is_stock:
                    rows = session_bars(rows)
            symbol = str(instrument)
            name = await name_cache.get_or_build(
                symbol, lambda: request.state["trading"].asset_name(symbol)
            )
            return Read(
                data=Chart(
                    name=name,
                    displayFromAt=display_at.isoformat(),
                    averages=bar_averages(rows, dashboard_section.sma_lengths),
                    bars=rows,
                ),
                read_at=read_at,
            )

        key = (instrument, timeframe, display_at, end_at)
        read = await bar_cache.get_or_build(key, build)
        return _read_response(read, dashboard_section.chart_max_age_seconds)

    @router.get("/api/levels")
    async def levels(
        request: AppRequest,
        reported: Annotated[ReportedRules, Depends(_reported_rules)],
        instrument: Annotated[Asset, Depends(_query_asset)],
        strategy_key: Annotated[StrategyKey | Unattributed, Query()],
        side: Annotated[Literal["long", "short"], Query()],
        entry: Annotated[float, Query(gt=0)],
        opened_on: Annotated[date, Query(alias="opened")],
    ) -> JSONResponse:
        if strategy_key == UNATTRIBUTED or instrument.asset_type != AssetType.STOCK:
            return _read_response(
                Read(data=Levels(strategy_key=strategy_key), read_at=datetime.now(UTC)),
                dashboard_section.levels_max_age_seconds,
            )

        async def build() -> Read[Levels]:
            read_at = datetime.now(UTC)
            payload = await build_levels(
                request.state["bars"],
                dashboard_section,
                reported.rules,
                instrument,
                strategy_key,
                side,
                entry,
                opened_on,
            )
            return Read(data=payload, read_at=read_at)

        key = (instrument, strategy_key, side, entry, opened_on)
        read = await levels_cache.get_or_build(key, build)
        return _read_response(read, dashboard_section.levels_max_age_seconds)

    @router.get("/api/strategies")
    async def strategies(
        reported: Annotated[ReportedRules, Depends(_reported_rules)],
    ) -> JSONResponse:
        read_at = reported.state.heartbeat_at if reported.state else datetime.now(UTC)
        return _read_response(
            Read(
                data=strategy_rules(reported.rules, is_reported=reported.is_reported),
                read_at=read_at,
            ),
            dashboard_section.strategies_max_age_seconds,
        )

    @router.get("/api/ledger")
    async def ledger(
        request: AppRequest, reported: Annotated[ReportedRules, Depends(_reported_rules)]
    ) -> JSONResponse:
        async def build() -> Read[Ledger]:
            account = await read_account(request)
            session_on = upcoming_session_on(today_on())
            daily = await equity_cache.get_or_build(
                session_on,
                lambda: request.state["trading"].equity(
                    dashboard_section.equity_daily_period, dashboard_section.equity_daily_timeframe
                ),
            )
            result = await build_ledger(
                account,
                request.state["trading"],
                request.state["bars"],
                settings.benchmark_symbol,
                dashboard_section,
                daily,
            )
            return Read(data=result, read_at=account.read_at)

        read = await ledger_cache.get_or_build(LEDGER_KEY, build)
        risk = reported.rules.risk
        return _read_response(
            Read(
                data={
                    **read.data,
                    "bot": bot_state(reported.state, heartbeat_timeout),
                    "windows": entry_windows(reported.rules),
                    "positionCapUsd": risk.notional_usd_max,
                    "dailyLossLimitPct": round(100 * risk.per_day_max, 2),
                },
                read_at=read.read_at,
            ),
            dashboard_section.ledger_max_age_seconds,
        )

    @router.get("/api/snapshot")
    async def snapshot(request: AppRequest) -> JSONResponse:
        account = await read_account(request)
        current = build_snapshot(account)
        held = ledger_cache.get(LEDGER_KEY)
        if held is not None and {row["symbol"] for row in held.data["positions"]} != {
            row["symbol"] for row in current["positions"]
        }:
            ledger_cache.drop(LEDGER_KEY)
        return _read_response(Read(data=current, read_at=account.read_at), 0)

    return router


def _read_response(read: Read[Any], max_age_seconds: int) -> JSONResponse:
    content = {"data": read.data, "read_at": read.read_at}
    return JSONResponse(
        jsonable_encoder(content),
        headers={"Cache-Control": f"private, max-age={max_age_seconds}, must-revalidate"},
    )


def _query_asset(symbol: Annotated[Symbol, Query()]) -> Asset:
    try:
        asset = Asset.from_symbol(symbol)
        check_supported_asset(asset)
    except ValueError as error:
        raise HTTPException(422, "The asset is invalid", headers=NO_STORE) from error
    return asset


async def _reported_rules(request: AppRequest) -> ReportedRules:
    state = await read_state(request.state["store"])
    return ReportedRules(state=state, rules=state.rules if state else settings)
