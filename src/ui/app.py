import hmac
import secrets
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from starlette.middleware.sessions import SessionMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from ui.alpaca import PAPER_API_URL, AlpacaReadClient
from ui.auth import RailwayOAuthClient
from ui.config import WebSettings
from ui.dashboard import NO_STORE, RuntimeStore, create_dashboard_router, error_response


PUBLIC_PATHS = frozenset({"/healthz", "/login", "/auth/callback", "/internal/state"})
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


class SessionGuardMiddleware:
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


def create_app() -> FastAPI:
    configuration = WebSettings()  # pyright: ignore[reportCallIssue]
    oauth_client = RailwayOAuthClient(configuration)
    runtime_store = RuntimeStore()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[dict[str, AlpacaReadClient]]:
        headers = {
            "APCA-API-KEY-ID": configuration.alpaca_api_key.get_secret_value(),
            "APCA-API-SECRET-KEY": configuration.alpaca_api_secret.get_secret_value(),
        }
        async with httpx.AsyncClient(
            base_url=PAPER_API_URL,
            headers=headers,
            timeout=httpx.Timeout(connect=1, read=3, write=3, pool=3),
        ) as client:
            yield {"alpaca": AlpacaReadClient(client)}

    app = FastAPI(
        title="Money Tree", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan
    )
    app.add_middleware(SessionGuardMiddleware)
    app.add_middleware(
        SessionMiddleware,
        secret_key=configuration.session_secret.get_secret_value(),
        session_cookie="money_tree_session",
        max_age=configuration.session_ttl_seconds,
        same_site="lax",
        https_only=True,
    )

    @app.exception_handler(httpx.HTTPError)
    async def upstream_failed(_: Request, error: Exception) -> JSONResponse:
        if not isinstance(error, httpx.HTTPStatusError) or error.response.status_code != 429:
            return error_response("Upstream read failed", 502)
        retry_after = error.response.headers.get("Retry-After", "60")[:40]
        return error_response("Alpaca read limit was reached", 503, {"Retry-After": retry_after})

    @app.get("/healthz")
    async def health() -> JSONResponse:
        return JSONResponse({"status": "ok"}, headers=NO_STORE)

    @app.get("/login")
    async def login(request: Request) -> RedirectResponse:
        authorization = oauth_client.authorization_request()
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
        if not isinstance(expected_state, str) or not isinstance(verifier, str) or state is None:
            return error_response("OAuth state is invalid", 400)
        if not hmac.compare_digest(expected_state.encode(), state.encode()):
            return error_response("OAuth state is invalid", 400)
        if not code:
            return error_response("OAuth code is missing", 400)
        identity = await oauth_client.identify(code, verifier)
        if identity.email.strip().casefold() not in configuration.allowed_railway_emails:
            return error_response("Railway user is not allowed", 403)
        request.session["user_sub"] = identity.subject
        request.session["csrf_token"] = secrets.token_urlsafe(32)
        return RedirectResponse("/", status_code=303, headers=NO_STORE)

    @app.post("/logout", status_code=204)
    async def logout(request: Request) -> Response:
        request.session.clear()
        return Response(
            status_code=204, headers={**NO_STORE, "Clear-Site-Data": '"cache", "storage"'}
        )

    app.include_router(create_dashboard_router(configuration, runtime_store))

    return app
