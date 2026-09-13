import asyncio
import hmac
import secrets
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import assert_never, cast

import httpx
import httpx2
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from redis.asyncio import Redis as AsyncRedis
from starlette.middleware.sessions import SessionMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from mt.data.alpaca import (
    TradingClientAlpaca,
    credential_headers,
    trading_api_url,
)
from mt.data.bars import BarsClientAlpaca, bars_api_url
from mt.data.http import RequestTransport, http_timeout
from mt.data.railway import RailwayOAuthClient
from mt.rules.settings import LoginSettings, WebSettings
from mt.rules.shared import settings

from .routes import NO_STORE, dashboard_router, error_response


PUBLIC_PATHS = frozenset({"/healthz", "/login", "/auth/callback"})
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


class LoginGuardMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] in PUBLIC_PATHS:
            await self._app(scope, receive, send)
            return
        session = scope.get("session", {})
        if not isinstance(subject := session.get("user_sub"), str) or not subject:
            redirects = scope["method"] in {"GET", "HEAD"} and not scope["path"].startswith("/api/")
            rejection: Response = (
                RedirectResponse("/login", status_code=303, headers=NO_STORE)
                if redirects
                else error_response("Authentication is required", 401)
            )
            await rejection(scope, receive, send)
            return
        if scope["method"] not in SAFE_METHODS:
            csrf_token = session.get("csrf_token")
            request_token = dict(scope["headers"]).get(b"x-csrf-token", b"")
            if not isinstance(csrf_token, str) or not hmac.compare_digest(
                csrf_token.encode(), request_token
            ):
                response = error_response("CSRF token is invalid", 403)
                await response(scope, receive, send)
                return
        await self._app(scope, receive, send)


def _start_login(request: Request, subject: str) -> None:
    request.session.clear()
    request.session["user_sub"] = subject
    request.session["csrf_token"] = secrets.token_urlsafe(32)


def create_app() -> FastAPI:
    configuration = WebSettings()  # pyright: ignore[reportCallIssue]

    credentials = credential_headers(settings.broker)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[dict[str, object]]:
        requests = configuration.requests
        concurrency = asyncio.Semaphore(requests.web_concurrency_max)
        async with (
            AsyncRedis.from_url(  # pyright: ignore[reportUnknownMemberType]
                str(settings.redis.url), decode_responses=True
            ) as state,
            httpx.AsyncClient(
                transport=RequestTransport(
                    requests.web_reads_per_minute, concurrency, requests.pause_seconds
                ),
                base_url=trading_api_url(settings.broker),
                headers=credentials,
                timeout=http_timeout(settings.broker.timeout),
            ) as trading,
            httpx.AsyncClient(
                transport=RequestTransport(
                    requests.web_market_data_per_minute, concurrency, requests.pause_seconds
                ),
                base_url=bars_api_url(),
                headers=credentials,
                timeout=http_timeout(settings.bars.timeout),
            ) as bars,
        ):
            yield {
                "state": state,
                "trading": TradingClientAlpaca(
                    trading,
                    configuration.dashboard,
                ),
                "bars": BarsClientAlpaca(
                    bars,
                    settings.bars,
                ),
            }

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
    @app.exception_handler(httpx.HTTPError)
    async def upstream_failed(_: Request, error: Exception) -> JSONResponse:
        if not isinstance(error, httpx.HTTPStatusError) or error.response.status_code != 429:
            return error_response("Upstream read failed", 502)
        retry_after = error.response.headers["Retry-After"]
        return error_response("Alpaca read limit was reached", 503, {"Retry-After": retry_after})

    @app.exception_handler(ExceptionGroup)
    async def upstream_group_failed(request: Request, error: Exception) -> JSONResponse:
        def leaves(group: BaseException) -> list[BaseException]:
            if isinstance(group, BaseExceptionGroup):
                return [
                    leaf
                    for child in cast(BaseExceptionGroup[BaseException], group).exceptions
                    for leaf in leaves(child)
                ]
            return [group]

        errors = leaves(error)
        if not all(isinstance(item, httpx.HTTPError) for item in errors):
            raise error
        limited = next(
            (
                item
                for item in errors
                if isinstance(item, httpx.HTTPStatusError) and item.response.status_code == 429
            ),
            None,
        )
        return await upstream_failed(request, limited or error)

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
            oauth = LoginSettings().login  # pyright: ignore[reportCallIssue]
            oauth_client = RailwayOAuthClient(oauth, configuration.oauth_redirect_uri)

            @app.get("/login")
            async def login(request: Request) -> RedirectResponse:
                authorization = await oauth_client.authorization_request()
                request.session.clear()
                request.session["oauth_state"] = authorization.state
                request.session["oauth_verifier"] = authorization.verifier
                return RedirectResponse(authorization.url, status_code=303, headers=NO_STORE)

            @app.get("/auth/callback")
            async def callback(
                request: Request,
                code: str | None = None,
                state: str | None = None,
                error: str | None = None,
            ) -> Response:
                expected_state = request.session.pop("oauth_state", None)
                verifier = request.session.pop("oauth_verifier", None)
                request.session.clear()
                if error is not None:
                    return error_response("Railway login was denied", 401)
                if (
                    not isinstance(expected_state, str)
                    or not isinstance(verifier, str)
                    or state is None
                ):
                    return error_response("OAuth state is invalid", 400)
                if not hmac.compare_digest(expected_state.encode(), state.encode()):
                    return error_response("OAuth state is invalid", 400)
                if not code:
                    return error_response("OAuth code is missing", 400)
                identity = await oauth_client.identify(code, verifier)
                if identity.email.strip().casefold() not in oauth.allowed_emails:
                    return error_response("Railway user is not allowed", 403)
                _start_login(request, identity.subject)
                return RedirectResponse("/", status_code=303, headers=NO_STORE)

        case _:
            assert_never(configuration.mode)

    @app.post("/logout", status_code=204)
    async def logout(request: Request) -> Response:
        request.session.clear()
        return Response(
            status_code=204, headers={**NO_STORE, "Clear-Site-Data": '"cache", "storage"'}
        )

    app.include_router(dashboard_router(configuration))

    return app
