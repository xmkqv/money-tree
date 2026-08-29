import hashlib
import re
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from tests.world.index import (
    authenticate,
    runtime_snapshot,
    set_session,
    sign_body,
    sign_snapshot,
    web_client,
)
from ui.alpaca import AlpacaReadClient
from ui.auth import RailwayIdentity, RailwayOAuthClient
from ui.dashboard import ASSET_DIRECTORY, ASSET_REWRITES, RUNTIME_BODY_BYTES_MAX


def test_health_is_public_when_session_is_absent() -> None:
    with web_client() as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["cache-control"] == "no-store"


def test_dashboard_redirects_to_login_when_session_is_absent() -> None:
    with web_client() as client:
        response = client.get("/", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    assert response.headers["cache-control"] == "no-store"


def test_api_rejects_request_when_session_is_absent() -> None:
    with web_client() as client:
        response = client.get("/api/account")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication is required"}


def test_dashboard_and_assets_render_when_session_is_authenticated() -> None:
    with web_client() as client:
        authenticate(client)
        dashboard = client.get("/")
        served = re.findall(r'/assets/[^"]+', dashboard.text)
        assets = {url: client.get(url) for url in served}

    assert dashboard.status_code == 200
    assert "PAPER" in dashboard.text
    assert "frame-ancestors 'none'" in dashboard.headers["content-security-policy"]
    expected = sorted(url.decode() for url in ASSET_REWRITES.values())
    assert sorted(assets) == expected
    for url, response in assets.items():
        assert response.status_code == 200, url
        assert response.headers["cache-control"] == "public, max-age=31536000, immutable"


def test_asset_urls_carry_a_digest_so_a_changed_file_is_never_served_from_cache() -> None:
    """Immutable caching is only safe while the URL tracks the contents."""
    served = {name: url for name, url in ASSET_REWRITES.items()}
    assert served, "expected at least one fingerprinted asset"
    for plain, fingerprinted in served.items():
        name = plain.decode().rsplit("/", 1)[-1]
        stem, _, suffix = name.rpartition(".")
        digest = fingerprinted.decode().rsplit("/", 1)[-1]
        assert digest.startswith(f"{stem}.") and digest.endswith(f".{suffix}")
        assert re.fullmatch(rf"{re.escape(stem)}\.[0-9a-f]{{12}}\.{re.escape(suffix)}", digest)

    contents = (ASSET_DIRECTORY / "dashboard.css").read_bytes()
    changed = hashlib.sha256(contents + b"/* edit */").hexdigest()[:12]
    assert changed not in ASSET_REWRITES[b"/assets/dashboard.css"].decode()


def test_unknown_asset_is_not_served() -> None:
    with web_client() as client:
        authenticate(client)
        missing = client.get("/assets/dashboard.css")
        traversal = client.get("/assets/..%2f..%2fpyproject.toml")

    assert missing.status_code == 404
    assert traversal.status_code == 404


def test_session_returns_csrf_token_when_session_is_authenticated() -> None:
    with web_client() as client:
        authenticate(client, "expected-token")
        response = client.get("/api/session")

    assert response.status_code == 200
    assert response.json() == {"csrf_token": "expected-token"}


def test_mutation_is_rejected_when_csrf_token_is_missing() -> None:
    with web_client() as client:
        authenticate(client, "expected-token")
        response = client.post("/logout")

    assert response.status_code == 403
    assert response.json() == {"detail": "CSRF token is invalid"}


def test_logout_clears_session_when_csrf_token_matches() -> None:
    with web_client() as client:
        authenticate(client, "expected-token")
        response = client.post("/logout", headers={"X-CSRF-Token": "expected-token"})

    assert response.status_code == 204
    assert response.headers["clear-site-data"] == '"cache", "storage"'
    assert "money_tree_session=null" in response.headers["set-cookie"]


def test_oauth_callback_creates_session_when_identity_is_allowed() -> None:
    async def identify(client: RailwayOAuthClient, code: str, verifier: str) -> RailwayIdentity:
        assert code == "code"
        assert verifier == "verifier"
        return RailwayIdentity("operator", "operator@example.com")

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(RailwayOAuthClient, "identify", identify)
        with web_client() as client:
            set_session(client, {"oauth_state": "expected", "oauth_verifier": "verifier"})
            callback = client.get("/auth/callback?code=code&state=expected", follow_redirects=False)
            session = client.get("/api/session")

    assert callback.status_code == 303
    assert callback.headers["location"] == "/"
    assert session.status_code == 200
    assert len(session.json()["csrf_token"]) >= 32


@pytest.mark.parametrize(
    ("query", "status_code", "detail"),
    [
        ("error=access_denied", 401, "Railway login was denied"),
        ("code=code&state=unexpected", 400, "OAuth state is invalid"),
        ("state=expected", 400, "OAuth code is missing"),
    ],
)
def test_oauth_callback_is_rejected_when_protocol_is_invalid(
    query: str, status_code: int, detail: str
) -> None:
    with web_client() as client:
        set_session(client, {"oauth_state": "expected", "oauth_verifier": "verifier"})
        response = client.get(f"/auth/callback?{query}")

    assert response.status_code == status_code
    assert response.json() == {"detail": detail}


def test_runtime_snapshot_is_available_when_signed_publish_is_valid() -> None:
    snapshot = runtime_snapshot()
    with web_client() as client:
        published = client.post(
            "/internal/state",
            content=sign_snapshot(snapshot),
            headers={"Content-Type": "application/octet-stream"},
        )
        authenticate(client)
        runtime = client.get("/api/run")
        events = client.get("/api/events")

    assert published.status_code == 204
    assert runtime.status_code == 200
    assert runtime.json()["data"]["sequence"] == 1
    assert runtime.json()["stale"] is False
    assert events.json()["data"][0]["message"] == "Trading run is active"


def test_runtime_snapshot_is_rejected_when_signature_is_invalid() -> None:
    with web_client() as client:
        response = client.post("/internal/state", content=b"unsigned")

    assert response.status_code == 401
    assert response.json() == {"detail": "Runtime signature is invalid"}


def test_runtime_snapshot_is_rejected_when_signature_is_expired() -> None:
    with web_client() as client:
        response = client.post(
            "/internal/state", content=sign_snapshot(runtime_snapshot(), expired=True)
        )

    assert response.status_code == 401
    assert response.json() == {"detail": "Runtime signature has expired"}


def test_runtime_snapshot_is_rejected_when_payload_is_invalid() -> None:
    with web_client() as client:
        response = client.post("/internal/state", content=sign_body(b"{}"))

    assert response.status_code == 422
    assert response.json() == {"detail": "Runtime snapshot is invalid"}


def test_runtime_snapshot_is_rejected_when_payload_is_too_large() -> None:
    with web_client() as client:
        response = client.post(
            "/internal/state", content=sign_body(b"x" * (RUNTIME_BODY_BYTES_MAX + 1))
        )

    assert response.status_code == 413
    assert response.json() == {"detail": "Runtime snapshot is too large"}


def test_runtime_snapshot_is_rejected_when_heartbeat_differs_from_signature_time() -> None:
    snapshot = runtime_snapshot(heartbeat_at=datetime.now(UTC) - timedelta(minutes=2))
    with web_client() as client:
        response = client.post("/internal/state", content=sign_snapshot(snapshot))

    assert response.status_code == 422
    assert response.json() == {"detail": "Runtime snapshot is invalid"}


def test_runtime_snapshot_is_rejected_when_sequence_is_replayed() -> None:
    payload = sign_snapshot(runtime_snapshot())
    with web_client() as client:
        accepted = client.post("/internal/state", content=payload)
        replayed = client.post("/internal/state", content=payload)

    assert accepted.status_code == 204
    assert replayed.status_code == 409
    assert replayed.json() == {"detail": "Runtime snapshot is not new"}


def test_account_response_is_cached_briefly_when_upstream_succeeds() -> None:
    async def account(client: AlpacaReadClient) -> dict[str, str]:
        return {"equity": "100000.00"}

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(AlpacaReadClient, "account", account)
        with web_client() as client:
            authenticate(client)
            response = client.get("/api/account")

    assert response.status_code == 200
    assert response.json()["data"] == {"equity": "100000.00"}
    assert response.headers["cache-control"] == "private, max-age=5, must-revalidate"


def test_account_response_is_rejected_when_upstream_fails() -> None:
    async def account(client: AlpacaReadClient) -> dict[str, str]:
        request = httpx.Request("GET", "https://paper-api.alpaca.markets/v2/account")
        raise httpx.ConnectError("unavailable", request=request)

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(AlpacaReadClient, "account", account)
        with web_client() as client:
            authenticate(client)
            response = client.get("/api/account")

    assert response.status_code == 502
    assert response.json() == {"detail": "Upstream read failed"}


def test_bars_rejects_a_symbol_that_is_not_a_ticker() -> None:
    """The symbol reaches an upstream path, so it is constrained at the edge."""
    with web_client() as client:
        authenticate(client)
        responses = {
            name: client.get(
                "/api/bars",
                params={
                    "symbol": name,
                    "timeframe": "5Min",
                    "opened": "2026-08-27",
                    "closed": "2026-08-27",
                },
            ).status_code
            for name in ("../secrets", "nvda", "N V", "", "A" * 40)
        }

    assert all(status == 422 for status in responses.values()), responses


def test_bars_rejects_an_unknown_timeframe_and_a_reversed_window() -> None:
    with web_client() as client:
        authenticate(client)
        timeframe = client.get(
            "/api/bars",
            params={
                "symbol": "NVDA",
                "timeframe": "1Min",
                "opened": "2026-08-27",
                "closed": "2026-08-27",
            },
        )
        reversed_window = client.get(
            "/api/bars",
            params={
                "symbol": "NVDA",
                "timeframe": "5Min",
                "opened": "2026-08-28",
                "closed": "2026-08-27",
            },
        )

    assert timeframe.status_code == 422
    assert reversed_window.status_code == 422


def test_bars_requires_a_session() -> None:
    with web_client() as client:
        response = client.get(
            "/api/bars",
            params={
                "symbol": "NVDA",
                "timeframe": "5Min",
                "opened": "2026-08-27",
                "closed": "2026-08-27",
            },
        )

    assert response.status_code == 401
