import hashlib
import re
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from bot.types import RuntimeSnapshot
from tests.world.index import (
    authenticate,
    runtime_snapshot,
    set_session,
    sign_body,
    sign_snapshot,
    web_client,
)
from ui.alpaca import AlpacaMarketDataClient, AlpacaReadClient
from ui.auth import RailwayIdentity, RailwayOAuthClient
from ui.dashboard import (
    ASSET_DIRECTORY,
    ASSET_REWRITES,
    PULSE_TTL_SECONDS,
    RUN_TTL_SECONDS,
    RUNTIME_BODY_BYTES_MAX,
)


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


def test_the_page_links_a_tab_icon_that_survives_a_dark_tab_strip() -> None:
    """Black is right on a light tab strip and invisible on a dark one.

    The icon is one file for both, so it carries the switch itself; without it
    the tab would simply look empty for anyone running a dark browser.
    """
    with web_client() as client:
        authenticate(client)
        page = client.get("/")
        link = re.search(r'<link rel="icon" href="([^"]+)" type="([^"]+)">', page.text)
        assert link, "the page should declare a tab icon"
        icon = client.get(link.group(1))

    assert link.group(2) == "image/svg+xml"
    assert link.group(1).encode() in ASSET_REWRITES.values(), "the icon should be fingerprinted"
    assert icon.status_code == 200
    assert icon.headers["content-type"].startswith("image/svg+xml")
    ET.fromstring(icon.text)  # a malformed icon draws nothing at all
    assert "prefers-color-scheme: dark" in icon.text


def test_the_phone_breakpoint_is_the_same_width_in_both_the_sheet_and_the_script() -> None:
    """The phone layout is split across two files and has to agree with itself.

    The stylesheet stacks the page and hides the plots below one width; the
    script stops drawing them below another. Let those two drift apart and a
    phone gets either a plot drawn into a hidden box or a panel with a hole
    where the figures should be, neither of which shows up in a unit test.
    """
    sheet = (ASSET_DIRECTORY / "dashboard.css").read_text()
    script = (ASSET_DIRECTORY / "dashboard.js").read_text()

    styled = re.search(r"@media \(max-width: (\d+)px\) \{\n\n  :root \{", sheet)
    scripted = re.search(r'matchMedia\("\(max-width: (\d+)px\)"\)', script)

    assert styled, "the stylesheet should carry a phone layer"
    assert scripted, "the script should carry the same breakpoint"
    assert styled.group(1) == scripted.group(1)


def _phone_layer() -> str:
    """The phone media query with its commentary stripped out."""
    sheet = (ASSET_DIRECTORY / "dashboard.css").read_text()
    return re.sub(r"/\*.*?\*/", "", sheet[sheet.index("/* \u2550\u2550\u2550 phone") :], flags=re.S)


def test_the_phone_layout_keeps_every_view_the_wide_one_offers() -> None:
    """Stacking a page is allowed to move a control; it is not allowed to drop one.

    The phone layer hides the equity plot, whose figure the panel states in
    words beside it, and the mouse's instructions, which the touch note above
    them replaces. Anything else disappearing from a phone is a feature quietly
    lost, so the hidden set is named here rather than trusted.
    """
    phone = _phone_layer()
    hidden = {
        selector.strip()
        for block in re.findall(r"([^{}]+)\{[^{}]*display: none[^{}]*\}", phone)
        for selector in block.split(",")
    }

    assert hidden == {
        "#chart-host",  # the equity plot; its figures are painted regardless
        ".tc-hint",  # drag and scroll, written for a mouse
        ".status::-webkit-scrollbar",
        "table.trades thead",
        ".table-scroll table.data thead",
        "table.trades tbody td.key::before",
        ".table-scroll table.data tbody td.key::before",
        "table.trades tbody td.empty::before",
    }


def test_the_phone_hides_the_equity_plot_by_id_so_the_trade_plot_survives() -> None:
    """The trade chart is a .chart-host too, and it is the one plot a phone keeps.

    Hiding the equity plot by its class took the trade chart with it, silently:
    the panel still laid out, the script still fetched bars, and the host simply
    measured zero, which every guard in the drawing code reads as "too early to
    draw". Only the id may be hidden here.
    """
    page = (ASSET_DIRECTORY / "dashboard.html").read_text()
    assert 'class="chart-host trade-host" id="tc-host"' in page, (
        "the trade plot should still share the chart-host class this test guards"
    )

    for rule in re.findall(r"([^{}]+)\{[^{}]*display: none[^{}]*\}", _phone_layer()):
        for selector in rule.split(","):
            assert ".chart-host" not in selector, (
                f"{selector.strip()!r} would hide the trade chart as well"
            )


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


def test_the_pulse_requires_a_session_like_every_other_read() -> None:
    with web_client() as client:
        response = client.get("/api/pulse")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication is required"}


def test_the_pulse_is_shared_by_everyone_watching_and_never_cached_in_a_browser() -> None:
    """The cost is capped on the server, not in each viewer's cache.

    A per-browser cache would hold a figure past the two seconds it was true
    for, which is the one thing this read exists to avoid. The sharing has to
    happen upstream of that: one assembly answers every viewer inside the
    window, so a second watcher costs nothing and a stale figure is impossible.
    """
    reads: list[str] = []

    async def account(client: AlpacaReadClient) -> dict[str, str]:
        reads.append("account")
        return {"equity": "100000.00", "cash": "45802.41", "buying_power": "91605.00"}

    async def raw_positions(client: AlpacaReadClient) -> list[dict[str, str]]:
        return []

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(AlpacaReadClient, "account", account)
        monkeypatch.setattr(AlpacaReadClient, "raw_positions", raw_positions)
        with web_client() as client:
            authenticate(client)
            first = client.get("/api/pulse")
            second = client.get("/api/pulse")

    assert first.status_code == 200
    assert first.json()["data"]["equity"] == 100000.00
    assert second.json()["data"] == first.json()["data"]
    assert len(reads) == 1, "a second viewer inside the window should cost no upstream read"
    assert first.headers["cache-control"] == "private, max-age=0, must-revalidate"


def test_the_script_asks_for_a_pulse_no_faster_than_the_server_makes_one() -> None:
    """The poll interval and the cache window are set in two different files.

    Polling faster than the server assembles only hands every viewer the same
    answer twice and spends a request doing it. Polling slower wastes the
    freshness that was paid for upstream. They are meant to be the same number,
    so drift between them is caught here rather than in a rate-limit reply.
    """
    script = (ASSET_DIRECTORY / "dashboard.js").read_text()
    interval = re.search(r"const PULSE_MS = (\d+);", script)

    assert interval, "the script should carry a pulse interval"
    assert int(interval.group(1)) == PULSE_TTL_SECONDS * 1000


def test_every_tab_leads_to_a_view_the_script_can_switch_to() -> None:
    """A tab whose view the switcher never shows is a dead link on the nav bar.

    The tab, the panel and the switcher's own list live in two files, and a page
    added to two of the three looks finished until it is clicked.
    """
    page = (ASSET_DIRECTORY / "dashboard.html").read_text()
    script = (ASSET_DIRECTORY / "dashboard.js").read_text()

    tabs = set(re.findall(r'<button type="button" data-view="([a-z_]+)"', page))
    panels = set(re.findall(r'<div class="view(?: hidden)?" id="view-([a-z_]+)"', page))
    switched = set(
        re.findall(r'"([a-z_]+)"', re.search(r"for \(const id of \[([^\]]+)\]", script).group(1))
    )

    assert "insides" in tabs, "The Insides should be reachable from the nav bar"
    assert tabs <= panels, f"{tabs - panels} have a tab but no panel"
    assert tabs <= switched, f"{tabs - switched} have a tab the switcher never shows"


def test_the_insides_page_reads_the_run_and_not_the_broker() -> None:
    """It has to render when the broker read is failing — that is when it is wanted.

    The page once resolved engine names through the ledger's roster, so a failed
    Alpaca call left LIVE undefined and the whole page threw before painting a
    single event. The run snapshot needs no broker, so nothing here may depend
    on one.
    """
    script = (ASSET_DIRECTORY / "dashboard.js").read_text()
    block = script[script.index("function readInsides(") - 400 : script.index("/* ══ live feed")]

    assert '"/api/run"' in script, "the page should read the run snapshot"
    assert "LIVE && LIVE.strategies" in script, "the roster must be optional"
    for guarded in ("LEDGER", "ACCOUNT", "OPEN_POSITIONS"):
        assert guarded not in block, f"the insides page should not need {guarded}"


def test_the_insides_page_asks_no_faster_than_the_run_snapshot_is_cached() -> None:
    script = (ASSET_DIRECTORY / "dashboard.js").read_text()
    interval = re.search(r"const INSIDES_MS = (\d+);", script)

    assert interval, "the script should carry an insides interval"
    assert int(interval.group(1)) == RUN_TTL_SECONDS * 1000


def test_the_insides_page_quotes_the_event_count_the_bot_actually_keeps() -> None:
    """The page tells the reader how much history it is looking at.

    That number is the exporter's trim, in another file. If the bot starts
    keeping a different count the page would keep promising the old one, which
    is the sort of quiet lie this page exists to avoid.
    """
    script = (ASSET_DIRECTORY / "dashboard.js").read_text()
    kept = re.search(r"const EVENTS_KEPT = (\d+);", script)

    assert kept, "the script should say how many events the bot keeps"
    assert int(kept.group(1)) == RuntimeSnapshot.model_fields["events"].metadata[0].max_length


def test_the_pulse_sends_only_fields_the_page_patches_onto_its_own_state() -> None:
    """A pulse is applied by assignment, so an unread field is a silent no-op.

    The failure this catches is a figure added to the payload and never shown:
    the endpoint looks right, the page keeps painting the ledger's minute-old
    answer, and nothing anywhere says so.
    """
    script = (ASSET_DIRECTORY / "dashboard.js").read_text()
    applied = script[script.index("function applyPulse(") : script.index("function hovering(")]
    sent = {"asOf", "equity", "cash", "buyingPower", "marketValue", "unrealised"}

    unread = {field for field in sent if f"pulsed.{field}" not in applied}
    assert not unread, f"the page never reads {unread} out of a pulse"
    assert "pulsed.positions" in applied, "the marks should reach the open positions"


def _broker_stubs(held: list[dict[str, str]]) -> dict[str, object]:
    """The seven reads a ledger assembles from, over a roster the caller owns."""
    now = datetime.now(UTC)

    async def account(client: AlpacaReadClient) -> dict[str, str]:
        return {
            "account_number": "PA0",
            "status": "ACTIVE",
            "equity": "100000.00",
            "last_equity": "99000.00",
            "cash": "45000.00",
            "buying_power": "90000.00",
        }

    async def raw_positions(client: AlpacaReadClient) -> list[dict[str, str]]:
        return held

    async def raw_fills(client: AlpacaReadClient, after: str | None = None) -> list[dict[str, str]]:
        return []

    async def raw_closed_orders(
        client: AlpacaReadClient, after: str | None = None
    ) -> list[dict[str, str]]:
        return []

    async def equity(client: AlpacaReadClient, period: str, timeframe: str) -> dict[str, object]:
        return {"points": [{"timestamp": int(now.timestamp()), "equity": 100000.0}]}

    async def clock(client: AlpacaReadClient) -> dict[str, object]:
        return {"is_open": True, "next_open": now.isoformat()}

    async def daily_bars(client: object, symbol: str, start: str) -> list[dict[str, object]]:
        return []

    return {
        "account": account,
        "raw_positions": raw_positions,
        "raw_fills": raw_fills,
        "raw_closed_orders": raw_closed_orders,
        "equity": equity,
        "clock": clock,
        "daily_bars": daily_bars,
    }


def test_a_pulse_retires_a_ledger_that_no_longer_names_the_same_holdings() -> None:
    """A roster that has moved makes the cached assembly wrong, not merely old.

    A position opened since it was built has no strategy against it and a
    position closed since has no trade, and the ledger is the only read that can
    supply either. Left to expire, the page would show a half-described account
    for the rest of the minute. The pulse sees the change first, so it is what
    retires the assembly.
    """

    def position(symbol: str) -> dict[str, str]:
        return {
            "symbol": symbol,
            "side": "long",
            "qty": "10",
            "avg_entry_price": "100.00",
            "current_price": "101.00",
            "market_value": "1010.00",
            "unrealized_pl": "10.00",
            "unrealized_plpc": "0.01",
        }

    held = [position("NVDA"), position("AMD")]
    stubs = _broker_stubs(held)

    with pytest.MonkeyPatch.context() as monkeypatch:
        for name in (
            "account",
            "raw_positions",
            "raw_fills",
            "raw_closed_orders",
            "equity",
            "clock",
        ):
            monkeypatch.setattr(AlpacaReadClient, name, stubs[name])
        monkeypatch.setattr(AlpacaMarketDataClient, "daily_bars", stubs["daily_bars"])
        with web_client() as client:
            authenticate(client)
            first = client.get("/api/ledger")
            held.pop()
            stale = client.get("/api/ledger")
            client.get("/api/pulse")
            reassembled = client.get("/api/ledger")

    def symbols(response: httpx.Response) -> list[str]:
        return [row["symbol"] for row in response.json()["data"]["positions"]]

    assert symbols(first) == ["NVDA", "AMD"]
    assert symbols(stale) == ["NVDA", "AMD"], "the ledger should be cached, or this proves nothing"
    assert symbols(reassembled) == ["NVDA"], "the pulse should have retired the stale assembly"


def test_the_calendar_arrows_have_two_different_months_to_walk_between() -> None:
    """Both ends of their range were read off the last session.

    An arrow is disabled at the edge of the range, so a range one month wide
    disables both of them at the only month they can reach: the calendar opened
    on the latest session and would not move, in either direction, ever. The two
    bounds have to be derived from different dates — the month the account was
    funded in, and the current one — for there to be anywhere to go.
    """
    script = (ASSET_DIRECTORY / "dashboard.js").read_text()

    def bound(name: str) -> str:
        assigned = re.search(rf"\b{name} = (\{{.*?\}});", script, flags=re.S)
        assert assigned, f"the calendar should still carry {name}"
        return assigned.group(1)

    assert bound("FIRST_MONTH") != bound("LAST_MONTH"), (
        "both calendar bounds read the same month, so neither arrow can move"
    )
