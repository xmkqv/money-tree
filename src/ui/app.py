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
from ui.auth import IdentityClient, RailwayIdentityError, RailwayOAuthClient
from ui.config import WebSettings
from ui.dashboard import NO_STORE, RuntimeStore, create_dashboard_router, error_response


PUBLIC_PATHS = frozenset({"/healthz", "/login", "/auth/callback", "/internal/state"})
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


class SessionGuardMiddleware:
    def __init__(self, app: ASGIApp, configuration: WebSettings) -> None:
        self._app = app
        self._configuration = configuration

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        scope_type = scope["type"]
        if scope_type not in {"http", "websocket"}:
            await self._app(scope, receive, send)
            return
        path = scope["path"]
        if scope_type == "http" and path in PUBLIC_PATHS:
            await self._app(scope, receive, send)
            return
        session = scope.get("session", {})
        subject = session.get("user_sub")
        if not isinstance(subject, str) or subject not in self._configuration.allowed_subjects:
            await self._reject(scope, receive, send)
            return
        if scope_type == "http" and scope["method"] not in SAFE_METHODS:
            csrf_token = session.get("csrf_token")
            request_token = dict(scope["headers"]).get(b"x-csrf-token", b"")
            if not isinstance(csrf_token, str) or not hmac.compare_digest(
                csrf_token.encode(),
                request_token,
            ):
                response = error_response("CSRF token is invalid", 403)
                await response(scope, receive, send)
                return
        await self._app(scope, receive, send)

    async def _reject(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 4401})
            return
        if scope["path"].startswith("/api/"):
            response = error_response("Authentication is required", 401)
        elif scope["method"] in {"GET", "HEAD"}:
            response: Response = RedirectResponse(
                "/login",
                status_code=303,
                headers=NO_STORE,
            )
        else:
            response = error_response("Authentication is required", 401)
        await response(scope, receive, send)


def create_app(
    configuration: WebSettings | None = None,
    identity_client: IdentityClient | None = None,
) -> FastAPI:
    web_configuration = configuration or WebSettings()  # pyright: ignore[reportCallIssue]
    oauth_client = identity_client or RailwayOAuthClient(web_configuration)
    runtime_store = RuntimeStore()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[dict[str, AlpacaReadClient]]:
        timeout = httpx.Timeout(connect=1, read=3, write=3, pool=3)
        headers = {
            "APCA-API-KEY-ID": web_configuration.alpaca_api_key.get_secret_value(),
            "APCA-API-SECRET-KEY": web_configuration.alpaca_api_secret.get_secret_value(),
        }
        async with httpx.AsyncClient(
            base_url=PAPER_API_URL,
            headers=headers,
            timeout=timeout,
        ) as client:
            yield {"alpaca": AlpacaReadClient(client)}

    app = FastAPI(
        title="Money Tree",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.add_middleware(SessionGuardMiddleware, configuration=web_configuration)
    app.add_middleware(
        SessionMiddleware,
        secret_key=web_configuration.session_secret.get_secret_value(),
        session_cookie="money_tree_session",
        max_age=web_configuration.session_ttl_seconds,
        same_site="lax",
        https_only=True,
    )

    @app.get("/healthz")
    async def health() -> JSONResponse:
        return JSONResponse({"status": "ok"}, headers=NO_STORE)

    @app.get("/login")
    async def login(request: Request) -> RedirectResponse:
        authorization = oauth_client.authorization_request()
        request.session.clear()
        request.session["oauth_state"] = authorization.state
        request.session["oauth_verifier"] = authorization.verifier
        return RedirectResponse(
            authorization.url,
            status_code=303,
            headers=NO_STORE,
        )

    @app.get("/auth/callback")
    async def callback(
        request: Request,
        code: str | None = None,
        state: str | None = None,
        error: str | None = None,
    ) -> Response:
        expected_state = request.session.pop("oauth_state", None)
        verifier = request.session.pop("oauth_verifier", None)
        if error is not None:
            request.session.clear()
            return error_response("Railway login was denied", 401)
        if not isinstance(expected_state, str) or not isinstance(state, str):
            request.session.clear()
            return error_response("OAuth state is invalid", 400)
        if not hmac.compare_digest(
            expected_state.encode(),
            state.encode(),
        ) or not isinstance(verifier, str):
            request.session.clear()
            return error_response("OAuth state is invalid", 400)
        if not isinstance(code, str) or not code:
            request.session.clear()
            return error_response("OAuth code is missing", 400)
        try:
            subject = await oauth_client.identify(code, verifier)
        except RailwayIdentityError:
            request.session.clear()
            return error_response("Railway login failed", 502)
        if subject not in web_configuration.allowed_subjects:
            request.session.clear()
            return error_response("Railway user is not allowed", 403)
        request.session.clear()
        request.session["user_sub"] = subject
        request.session["csrf_token"] = secrets.token_urlsafe(32)
        return RedirectResponse("/", status_code=303, headers=NO_STORE)

    @app.post("/logout", status_code=204)
    async def logout(request: Request) -> Response:
        request.session.clear()
        return Response(
            status_code=204,
            headers={
                **NO_STORE,
                "Clear-Site-Data": '"cache", "storage"',
            },
        )

    app.include_router(create_dashboard_router(web_configuration, runtime_store))

    return app
