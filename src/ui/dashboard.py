import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from itsdangerous import BadSignature, SignatureExpired, TimestampSigner
from pydantic import AwareDatetime, ValidationError
from starlette.responses import FileResponse

from bot.types import STATE_SIGNATURE_SALT, RuntimeSnapshot
from ui.alpaca import AlpacaReadClient
from ui.config import WebSettings


ASSET_DIRECTORY = Path(__file__).with_name("assets")
DASHBOARD_HTML = (ASSET_DIRECTORY / "dashboard.v3.html").read_bytes()
DASHBOARD_CSS = ASSET_DIRECTORY / "dashboard.v3.css"
DASHBOARD_JAVASCRIPT = ASSET_DIRECTORY / "dashboard.v3.js"
NO_STORE = {"Cache-Control": "no-store"}
IMMUTABLE = {"Cache-Control": "public, max-age=31536000, immutable"}
HEARTBEAT_TIMEOUT = timedelta(seconds=15)
SIGNATURE_WINDOW_SECONDS = 30
RUNTIME_BODY_BYTES_MAX = 65_536
RUNTIME_SIGNATURE_ENVELOPE_BYTES = 51
RUNTIME_REQUEST_BYTES_MAX = RUNTIME_BODY_BYTES_MAX + RUNTIME_SIGNATURE_ENVELOPE_BYTES
PORTFOLIO_TIMEFRAMES = {"1D": "5Min", "1W": "15Min", "1M": "1D", "1A": "1D"}
DASHBOARD_HEADERS = {
    "Cache-Control": "private, no-cache",
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self' https://unpkg.com; "
        "style-src 'self' https://unpkg.com; connect-src 'self'; img-src 'self' data:; "
        "object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
    ),
}


class RuntimeStore:
    def __init__(self) -> None:
        self._snapshot: RuntimeSnapshot | None = None

    def publish(self, snapshot: RuntimeSnapshot) -> bool:
        current = self._snapshot
        if current is not None:
            if snapshot.run_id == current.run_id and snapshot.sequence <= current.sequence:
                return False
            if snapshot.run_id != current.run_id and snapshot.started_at <= current.started_at:
                return False
        self._snapshot = snapshot
        return True

    def read(self) -> RuntimeSnapshot | None:
        return self._snapshot


def error_response(
    detail: str, status_code: int, headers: dict[str, str] | None = None
) -> JSONResponse:
    return JSONResponse(
        {"detail": detail}, status_code=status_code, headers={**NO_STORE, **(headers or {})}
    )


def read_response(data: Any, max_age: int, **metadata: Any) -> JSONResponse:
    content = {"data": data, "read_at": datetime.now(UTC), **metadata}
    return JSONResponse(
        jsonable_encoder(content),
        headers={"Cache-Control": f"private, max-age={max_age}, must-revalidate", "Vary": "Cookie"},
    )


def create_dashboard_router(configuration: WebSettings, runtime_store: RuntimeStore) -> APIRouter:
    router = APIRouter()
    mode = b"PAPER" if configuration.alpaca_is_paper else b"LIVE"
    dashboard_html = DASHBOARD_HTML.replace(b"{{ ALPACA_MODE }}", mode)
    signer = TimestampSigner(
        configuration.state_export_secret.get_secret_value(),
        salt=STATE_SIGNATURE_SALT,
        digest_method=hashlib.sha256,
    )

    def alpaca(request: Request) -> AlpacaReadClient:
        return request.state.alpaca

    def runtime_state() -> tuple[RuntimeSnapshot | None, bool]:
        snapshot = runtime_store.read()
        stale = snapshot is None or datetime.now(UTC) - snapshot.heartbeat_at > HEARTBEAT_TIMEOUT
        return snapshot, stale

    @router.get("/")
    async def dashboard() -> Response:
        return Response(dashboard_html, media_type="text/html", headers=DASHBOARD_HEADERS)

    @router.get("/assets/dashboard.v3.css")
    async def dashboard_css() -> FileResponse:
        return FileResponse(DASHBOARD_CSS, media_type="text/css", headers=IMMUTABLE)

    @router.get("/assets/dashboard.v3.js")
    async def dashboard_javascript() -> FileResponse:
        return FileResponse(
            DASHBOARD_JAVASCRIPT,
            media_type="text/javascript",
            headers=IMMUTABLE,
        )

    @router.get("/api/session")
    async def session(request: Request) -> JSONResponse:
        token = request.session.get("csrf_token")
        if not isinstance(token, str):
            return error_response("Session is invalid", 401)
        return JSONResponse({"csrf_token": token}, headers=NO_STORE)

    @router.get("/api/account")
    async def account(request: Request) -> JSONResponse:
        return read_response(await alpaca(request).account(), 5)

    @router.get("/api/positions")
    async def positions(request: Request) -> JSONResponse:
        return read_response(await alpaca(request).positions(), 5)

    @router.get("/api/orders/open")
    async def open_orders(request: Request) -> JSONResponse:
        return read_response(await alpaca(request).orders("open", 100), 5)

    @router.get("/api/orders")
    async def orders(
        request: Request,
        limit: Annotated[int, Query(ge=1, le=100)] = 100,
        until: AwareDatetime | None = None,
    ) -> JSONResponse:
        max_age = 300 if until is not None else 15
        cursor = until.isoformat() if until is not None else None
        return read_response(await alpaca(request).orders("closed", limit, cursor), max_age)

    @router.get("/api/fills")
    async def fills(
        request: Request,
        limit: Annotated[int, Query(ge=1, le=100)] = 100,
        page_token: Annotated[
            str | None,
            Query(
                min_length=55,
                max_length=55,
                pattern=r"^[0-9]{17}::[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}$",
            ),
        ] = None,
    ) -> JSONResponse:
        max_age = 300 if page_token is not None else 15
        return read_response(await alpaca(request).fills(limit, page_token), max_age)

    @router.get("/api/equity")
    async def equity(
        request: Request, period: Literal["1D", "1W", "1M", "1A"] = "1D"
    ) -> JSONResponse:
        return read_response(await alpaca(request).equity(period, PORTFOLIO_TIMEFRAMES[period]), 60)

    @router.get("/api/run")
    async def runtime() -> JSONResponse:
        snapshot, stale = runtime_state()
        return read_response(snapshot, 5, stale=stale)

    @router.get("/api/events")
    async def events(limit: Annotated[int, Query(ge=1, le=50)] = 50) -> JSONResponse:
        snapshot, stale = runtime_state()
        data = list(reversed(snapshot.events[-limit:])) if snapshot else []
        return read_response(data, 5, stale=stale)

    @router.post("/internal/state", status_code=204)
    async def publish_runtime(request: Request) -> Response:
        chunks: list[bytes] = []
        size = 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > RUNTIME_REQUEST_BYTES_MAX:
                return error_response("Runtime snapshot is too large", 413)
            chunks.append(chunk)
        try:
            body, signed_at = signer.unsign(
                b"".join(chunks),
                max_age=SIGNATURE_WINDOW_SECONDS,
                return_timestamp=True,
            )
        except SignatureExpired:
            return error_response("Runtime signature has expired", 401)
        except BadSignature:
            return error_response("Runtime signature is invalid", 401)
        if len(body) > RUNTIME_BODY_BYTES_MAX:
            return error_response("Runtime snapshot is too large", 413)
        try:
            snapshot = RuntimeSnapshot.model_validate_json(body)
        except ValidationError:
            return error_response("Runtime snapshot is invalid", 422)
        drift = abs((snapshot.heartbeat_at - signed_at).total_seconds())
        if snapshot.started_at > snapshot.heartbeat_at or drift > SIGNATURE_WINDOW_SECONDS:
            return error_response("Runtime snapshot is invalid", 422)
        if not runtime_store.publish(snapshot):
            return error_response("Runtime snapshot is not new", 409)
        return Response(status_code=204, headers=NO_STORE)

    return router
