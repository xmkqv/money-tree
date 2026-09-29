# pyright: reportUnusedFunction=false
import asyncio
import hmac
import secrets
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import assert_never, cast

import httpx2
from alpaca.common.enums import BaseURL
from authlib.integrations.starlette_client import OAuthError
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from joserfc.errors import JoseError
from pydantic import ValidationError
from redis.asyncio import Redis as AsyncRedis
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import HTTPConnection
from starlette.types import ASGIApp, Receive, Scope, Send

from mt.data.alpaca import TradingClientAlpaca, credential_headers
from mt.data.bars import BarsClientAlpaca
from mt.data.http import RequestTransport, http_timeout
from mt.data.railway import Identity, railway_oauth
from mt.rules.settings import LoginSettings, WebSettings
from mt.rules.shared import settings

from .routes import NO_STORE, AppState, dashboard_router, error_response


class LoginGuardMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] in PUBLIC_PATHS:
            await self._app(scope, receive, send)
            return
        connection = HTTPConnection(scope)
        if not isinstance(subject := connection.session.get("user_sub"), str) or not subject:
            is_redirect = scope["method"] in {"GET", "HEAD"} and not scope["path"].startswith(
                "/api/"
            )
            rejection: Response = (
                RedirectResponse("/login", status_code=303, headers=NO_STORE)
                if is_redirect
                else error_response("Authentication is required", 401)
            )
            await rejection(scope, receive, send)
            return
        if scope["method"] not in SAFE_METHODS:
            csrf_token = connection.session.get("csrf_token")
            request_token = connection.headers.get("x-csrf-token", "")
            if not isinstance(csrf_token, str) or not hmac.compare_digest(
                csrf_token.encode(), request_token.encode()
            ):
                response = error_response("CSRF token is invalid", 403)
                await response(scope, receive, send)
                return
        await self._app(scope, receive, send)


PUBLIC_PATHS = frozenset({"/healthz", "/login", "/auth/callback"})
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def create_app() -> FastAPI:
    configuration = WebSettings()  # pyright: ignore[reportCallIssue]

    credentials = credential_headers(settings.broker)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[AppState]:
        requests = configuration.requests
        concurrency = asyncio.Semaphore(requests.web_concurrency_max)
        async with (
            AsyncRedis.from_url(  # pyright: ignore[reportUnknownMemberType]
                str(settings.redis.url), decode_responses=True
            ) as store,
            httpx2.AsyncClient(
                transport=RequestTransport(
                    requests.web_reads_per_minute, concurrency, requests.pause_seconds
                ),
                base_url=(
                    BaseURL.TRADING_PAPER if settings.broker.is_paper else BaseURL.TRADING_LIVE
                ).value,
                headers=credentials,
                timeout=http_timeout(settings.broker.timeout),
            ) as trading,
            httpx2.AsyncClient(
                transport=RequestTransport(
                    requests.web_market_data_per_minute, concurrency, requests.pause_seconds
                ),
                base_url=BaseURL.DATA.value,
                headers=credentials,
                timeout=http_timeout(settings.bars.timeout),
            ) as bars,
        ):
            yield AppState(
                store=store,
                trading=TradingClientAlpaca(trading, configuration.dashboard),
                bars=BarsClientAlpaca(bars, settings.bars),
            )

    app = FastAPI(
        title="Money Tree", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan
    )
    app.add_middleware(LoginGuardMiddleware)
    app.add_middleware(
        SessionMiddleware,
        secret_key=configuration.web.login_secret.get_secret_value(),
        session_cookie="money_tree_login",
        max_age=configuration.web.login_ttl_seconds,
        same_site="lax",
        https_only=configuration.mode == "production",
    )

    @app.exception_handler(httpx2.HTTPError)
    async def upstream_failed(_: Request, error: Exception) -> JSONResponse:
        if not isinstance(error, httpx2.HTTPStatusError) or error.response.status_code != 429:
            return error_response("Upstream read failed", 502)
        retry_after = error.response.headers.get("Retry-After")
        headers = {"Retry-After": retry_after} if retry_after is not None else None
        return error_response("Alpaca read limit was reached", 503, headers)

    @app.exception_handler(ExceptionGroup)
    async def upstream_group_failed(request: Request, error: Exception) -> JSONResponse:
        group = cast(ExceptionGroup[Exception], error)
        if not _is_http_only(group):
            raise group
        return await upstream_failed(request, _find_rate_limited(group) or group)

    @app.get("/healthz")
    async def health() -> JSONResponse:
        return JSONResponse({"status": "ok"}, headers=NO_STORE)

    match configuration.mode:
        case "development":

            @app.get("/login")
            async def login_locally(request: Request) -> RedirectResponse:
                _start_login(request, configuration.mode)
                return RedirectResponse("/", status_code=303, headers=NO_STORE)

        case "production":
            login = LoginSettings().login  # pyright: ignore[reportCallIssue]
            railway = railway_oauth(login)

            @app.get("/login")
            async def login_remotely(request: Request) -> RedirectResponse:
                request.session.clear()
                redirect = await railway.authorize_redirect(
                    request, configuration.web.oauth_redirect_uri
                )
                return RedirectResponse(
                    redirect.headers["location"], status_code=303, headers=NO_STORE
                )

            @app.get("/auth/callback")
            async def callback(request: Request) -> Response:
                try:
                    token = await railway.authorize_access_token(request)
                    identity = Identity.model_validate(await railway.userinfo(token=token))
                except OAuthError, JoseError:
                    return error_response("Railway login failed", 401)
                except ValidationError:
                    return error_response("Railway OAuth identity is invalid", 401)
                if identity.email not in login.allowed_emails:
                    return error_response("Railway user is not allowed", 403)
                _start_login(request, identity.sub)
                return RedirectResponse("/", status_code=303, headers=NO_STORE)

        case _:
            assert_never(configuration.mode)

    @app.post("/logout", status_code=204, response_class=Response)
    async def logout(request: Request, response: Response) -> None:
        request.session.clear()
        response.headers.update({**NO_STORE, "Clear-Site-Data": '"cache", "storage"'})

    app.include_router(dashboard_router(configuration))

    return app


def _start_login(request: Request, subject: str) -> None:
    request.session.clear()
    request.session["user_sub"] = subject
    request.session["csrf_token"] = secrets.token_urlsafe(32)


def _is_http_only(group: BaseExceptionGroup[BaseException]) -> bool:
    return (
        group.subgroup(lambda item: not isinstance(item, httpx2.HTTPError | BaseExceptionGroup))
        is None
    )


def _find_rate_limited(error: BaseException) -> httpx2.HTTPStatusError | None:
    if isinstance(error, BaseExceptionGroup):
        return next(
            (
                found
                for item in cast(BaseExceptionGroup[BaseException], error).exceptions
                if (found := _find_rate_limited(item)) is not None
            ),
            None,
        )
    if isinstance(error, httpx2.HTTPStatusError) and error.response.status_code == 429:
        return error
    return None
