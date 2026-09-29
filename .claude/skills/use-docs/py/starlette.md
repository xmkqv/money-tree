# [starlette][starlette:docs]

1.7.0 · itsdangerous 2.2 · anyio · Python 3.10+ syntax

```py
import hmac
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TypedDict

from starlette.applications import Starlette
from starlette.datastructures import MutableHeaders
from starlette.exceptions import HTTPException
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import HTTPConnection, Request
from starlette.responses import FileResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
from starlette.routing import Mount, Route, Router
from starlette.staticfiles import StaticFiles
from starlette.testclient import TestClient
from starlette.types import ASGIApp, Message, Receive, Scope, Send
```

[Pure ASGI middleware][starlette:middleware] → a class taking `app`, awaiting `app(scope, receive, send)`; wrap `send` to touch responses.

```py
class SecurityHeaders:
    def __init__(self, app: ASGIApp, *, policy: str) -> None:
        self.app = app
        self.policy = policy

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":  # lifespan and websocket scopes pass through untouched
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)  # mutates message["headers"] in place
                headers.setdefault("Content-Security-Policy", self.policy)
                headers.add_vary_header("Cookie")
            await send(message)

        await self.app(scope, receive, send_with_headers)
```

[`HTTPConnection(scope)`][starlette:requests] → read-only view of cookies, headers, session and state without a body; a `Response` is itself an ASGI app.

```py
class Guard:
    def __init__(self, app: ASGIApp, *, public: frozenset[str]) -> None:
        self.app = app
        self.public = public

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket") or scope["path"] in self.public:
            await self.app(scope, receive, send)
            return
        connection = HTTPConnection(scope)
        if not connection.session.get("member"):  # SessionMiddleware must wrap this class
            rejection = (
                RedirectResponse("/login", status_code=303)
                if scope["type"] == "http" and scope["method"] == "GET"
                else JSONResponse({"detail": "Authentication is required"}, status_code=401)
            )
            await rejection(scope, receive, send)  # websocket scopes need a websocket close instead
            return
        if scope["type"] == "http" and scope["method"] not in {"GET", "HEAD", "OPTIONS"}:
            expected = str(connection.session.get("csrf", ""))
            if not hmac.compare_digest(expected, connection.headers.get("x-csrf-token", "")):
                await JSONResponse({"detail": "CSRF token is invalid"}, status_code=403)(scope, receive, send)
                return
        await self.app(scope, receive, send)
```

[`SessionMiddleware(app, secret_key, ...)`][starlette:middleware] → signed, unencrypted client-side cookie holding JSON; `request.session` is a dict that tracks reads and writes.

```py
session = Middleware(
    SessionMiddleware,
    secret_key="change-me",  # str or starlette.datastructures.Secret; rotating it logs everyone out
    session_cookie="app_session",  # default "session"
    max_age=8 * 3600,  # None → browser-session cookie; also bounds the signature age on read
    path="/",
    same_site="lax",  # "lax" | "strict" | "none"
    https_only=True,  # adds Secure
    domain=None,
    partitioned=False,
)


async def login(request: Request) -> Response:
    request.session.clear()  # drop any prior identity before authenticating
    request.session["member"] = "id"  # a modified non-empty session sets the cookie
    return RedirectResponse("/", status_code=303)  # a cleared non-empty session expires it
```

[`Starlette(middleware=[...])`][starlette:applications] → list order is outermost first; `add_middleware` inserts at index 0, so the last one added is outermost.

```py
class State(TypedDict):
    pool: object


@asynccontextmanager
async def lifespan(app: Starlette) -> AsyncIterator[State]:
    async with open_pool() as pool:
        yield {"pool": pool}  # shallow-copied into every request's state


async def homepage(request: Request[State]) -> Response:
    return JSONResponse({"pool": repr(request.state["pool"])})


app = Starlette(
    routes=[Route("/", homepage), Mount("/static", StaticFiles(directory="static"), name="static")],
    middleware=[  # outermost → innermost; session must precede whatever reads it
        Middleware(TrustedHostMiddleware, allowed_hosts=["example.test", "*.example.test"]),
        Middleware(HTTPSRedirectMiddleware),
        session,
        Middleware(Guard, public=frozenset({"/login"})),
        Middleware(GZipMiddleware, minimum_size=1024),
        Middleware(SecurityHeaders, policy="default-src 'self'"),
    ],
    exception_handlers={HTTPException: http_error, 404: not_found},  # class or status code
    lifespan=lifespan,
    max_body_size=1_000_000,  # 413 above the limit; also on Route, Mount and Router
)
```

[`StaticFiles(directory=, packages=, html=, check_dir=, follow_symlink=)`][starlette:staticfiles] → ASGI app serving a directory with ETag, range and 304 handling; mount it, do not route it.

```py
static = StaticFiles(directory="static", check_dir=True)  # missing dir raises at construction
static_pkg = StaticFiles(packages=[("mypkg", "assets")])  # (package, subdirectory) ; default subdir "statics"
spa = StaticFiles(directory="dist", html=True)  # serves index.html for directories, 404.html on miss

routes = [
    Mount("/assets", app=static, name="assets"),
    Mount("/", app=spa),  # a root mount matches everything, so it goes last
]
url = app.url_path_for("assets", path="app.js")  # "/assets/app.js" ; in a handler: request.url_for(...)
```

[Responses][starlette:responses] → `Response(content, status_code, headers, media_type, background)`; `set_cookie` mirrors cookie attributes.

```py
async def stream(request: Request) -> Response:
    async def chunks() -> AsyncIterator[bytes]:
        async for row in rows():
            if await request.is_disconnected():
                return
            yield row

    response = StreamingResponse(chunks(), media_type="text/csv", headers={"Cache-Control": "no-store"})
    response.set_cookie(
        "seen", "1",
        max_age=600, expires=None, path="/", domain=None,
        secure=True, httponly=True, samesite="lax", partitioned=False,
    )
    response.delete_cookie("stale", path="/")  # path and domain must match the original cookie
    return response


download = FileResponse("report.pdf", filename="report.pdf")  # supports Range requests
moved = RedirectResponse("/new", status_code=308)  # default 307 keeps the method
```

[`Request`][starlette:requests] → `HTTPConnection` plus body access; the body can be consumed once as a stream or cached by `body()`.

```py
async def submit(request: Request) -> Response:
    request.method, request.url.path, request.query_params.get("q")
    request.headers.get("content-type"), request.cookies.get("theme"), request.path_params["id"]
    request.client  # Address(host, port) | None ; behind a proxy this is the proxy
    request.app.state, request.state["pool"], request.session  # session asserts SessionMiddleware

    payload = await request.json()  # or `await request.body()`, or `async for chunk in request.stream()`
    async with request.form(max_files=10, max_fields=100) as form:  # needs python-multipart
        upload = form["file"]
    return JSONResponse(payload)
```

[`BaseHTTPMiddleware` and built-ins][starlette:middleware] → `dispatch(request, call_next)` is convenient but wraps the body in a stream; prefer pure ASGI for streaming and header work.

```py
class Timing(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)  # a Response whose body is already a stream
        response.headers["X-Handled"] = "1"
        return response


# HTTPException is caught by ExceptionMiddleware (innermost); other exceptions reach
# ServerErrorMiddleware (outermost) which renders 500 and re-raises to the server.
async def http_error(request: Request, exc: HTTPException) -> Response:
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers)
```

[`TestClient(app, ...)`][starlette:testclient] → synchronous httpx client over ASGI; enter it as a context manager to run lifespan.

```py
def test_flow() -> None:
    with TestClient(
        app,
        base_url="https://testserver",  # Secure cookies are only replayed over https
        raise_server_exceptions=True,  # False → unhandled errors become 500 responses
        follow_redirects=False,  # the default is True
    ) as client:  # lifespan startup here, shutdown on exit
        reply = client.get("/login")
        assert reply.status_code == 303
        assert client.post("/x", headers={"X-CSRF-Token": "bad"}).status_code == 403
        with client.websocket_connect("/ws") as socket:
            socket.send_text("ping")
```

## refs

[starlette:docs]: https://starlette.dev/

[starlette:applications]: https://starlette.dev/applications/
    Cannot add middleware after an application has started

[starlette:middleware]: https://starlette.dev/middleware/
    This middleware is experimental.

[starlette:requests]: https://starlette.dev/requests/
    SessionMiddleware must be installed to access request.session

[starlette:responses]: https://starlette.dev/responses/

[starlette:staticfiles]: https://starlette.dev/staticfiles/

[starlette:routing]: https://starlette.dev/routing/
    Routed paths must start with '/'

[starlette:lifespan]: https://starlette.dev/lifespan/
    The server does not support "state" in the lifespan scope.
    Use one or the other, not both.

[starlette:exceptions]: https://starlette.dev/exceptions/
    Caught handled exception, but response already started.

[starlette:testclient]: https://starlette.dev/testclient/

[starlette:release-notes]: https://starlette.dev/release-notes/
