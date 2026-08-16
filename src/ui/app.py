import hmac
import secrets

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from starlette.middleware.sessions import SessionMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from ui.auth import IdentityClient, RailwayIdentityError, RailwayOAuthClient
from ui.config import WebSettings


PUBLIC_PATHS = frozenset({"/healthz", "/login", "/auth/callback"})
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


class SessionGuardMiddleware:
    def __init__(self, app: ASGIApp, configuration: WebSettings) -> None:
        self.app = app
        self.configuration = configuration

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        scope_type = scope["type"]
        if scope_type not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return
        path = scope["path"]
        if scope_type == "http" and path in PUBLIC_PATHS:
            await self.app(scope, receive, send)
            return
        session = scope.get("session", {})
        subject = session.get("user_sub")
        if not isinstance(subject, str) or subject not in self.configuration.allowed_subjects:
            await self._reject(scope, receive, send)
            return
        scope.setdefault("state", {})["user_sub"] = subject
        if scope_type == "http" and scope["method"] not in SAFE_METHODS:
            csrf_token = session.get("csrf_token")
            request_token = dict(scope["headers"]).get(b"x-csrf-token", b"").decode()
            if not isinstance(csrf_token, str) or not hmac.compare_digest(
                csrf_token,
                request_token,
            ):
                response = JSONResponse({"detail": "CSRF token is invalid"}, status_code=403)
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)

    async def _reject(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 4401})
            return
        if scope["method"] in {"GET", "HEAD"}:
            response: Response = RedirectResponse("/login", status_code=303)
        else:
            response = JSONResponse({"detail": "Authentication is required"}, status_code=401)
        await response(scope, receive, send)


def create_app(
    configuration: WebSettings | None = None,
    identity_client: IdentityClient | None = None,
) -> FastAPI:
    web_configuration = configuration or WebSettings()
    oauth_client = identity_client or RailwayOAuthClient(web_configuration)
    app = FastAPI(title="Money Tree", docs_url=None, redoc_url=None, openapi_url=None)
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
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/login")
    async def login(request: Request) -> RedirectResponse:
        authorization = RailwayOAuthClient(web_configuration).authorization_request()
        request.session.clear()
        request.session["oauth_state"] = authorization.state
        request.session["oauth_verifier"] = authorization.verifier
        return RedirectResponse(authorization.url, status_code=303)

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
            return JSONResponse({"detail": "Railway login was denied"}, status_code=401)
        if not isinstance(expected_state, str) or not isinstance(state, str):
            request.session.clear()
            return JSONResponse({"detail": "OAuth state is invalid"}, status_code=400)
        if not hmac.compare_digest(expected_state, state) or not isinstance(verifier, str):
            request.session.clear()
            return JSONResponse({"detail": "OAuth state is invalid"}, status_code=400)
        if not isinstance(code, str) or not code:
            request.session.clear()
            return JSONResponse({"detail": "OAuth code is missing"}, status_code=400)
        try:
            subject = await oauth_client.identify(code, verifier)
        except RailwayIdentityError:
            request.session.clear()
            return JSONResponse({"detail": "Railway login failed"}, status_code=502)
        if subject not in web_configuration.allowed_subjects:
            request.session.clear()
            return JSONResponse({"detail": "Railway user is not allowed"}, status_code=403)
        request.session.clear()
        request.session["user_sub"] = subject
        request.session["csrf_token"] = secrets.token_urlsafe(32)
        return RedirectResponse("/", status_code=303)

    @app.get("/")
    async def index(request: Request) -> dict[str, str | bool]:
        return {
            "app": "money-tree",
            "authenticated": True,
            "csrf_token": request.session["csrf_token"],
        }

    @app.post("/logout", status_code=204)
    async def logout(request: Request) -> Response:
        request.session.clear()
        return Response(status_code=204)

    return app
