import base64
import json
import unittest
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner
from starlette.websockets import WebSocketDisconnect

from ui.app import create_app
from ui.auth import RailwayIdentityError
from ui.config import WebSettings


SESSION_SECRET = "0123456789abcdef0123456789abcdef"


class FakeIdentityClient:
    def __init__(self, subject: str = "owner-sub", fails: bool = False) -> None:
        self.subject = subject
        self.fails = fails

    async def identify(self, code: str, verifier: str) -> str:
        if self.fails:
            raise RailwayIdentityError("test failure")
        return self.subject


def settings(**changes: object) -> WebSettings:
    values = {
        "app_base_url": "https://testserver",
        "railway_oauth_client_id": "client-id",
        "railway_oauth_client_secret": "client-secret",
        "railway_oauth_redirect_uri": "https://testserver/auth/callback",
        "allowed_railway_subs": "owner-sub,buddy-sub",
        "session_secret": SESSION_SECRET,
        "session_ttl_seconds": 28_800,
    }
    values.update(changes)
    return WebSettings(**values)


def begin_login(client: TestClient) -> str:
    response = client.get("/login", follow_redirects=False)
    query = parse_qs(urlsplit(response.headers["location"]).query)
    return query["state"][0]


def complete_login(client: TestClient, state: str) -> object:
    return client.get(
        "/auth/callback",
        params={"code": "authorization-code", "state": state},
        follow_redirects=False,
    )


class WebApplicationTest(unittest.TestCase):
    def client(self, subject: str = "owner-sub", fails: bool = False) -> TestClient:
        app = create_app(settings(), FakeIdentityClient(subject, fails))
        return TestClient(app, base_url="https://testserver")

    def test_health_is_public(self) -> None:
        with self.client() as client:
            response = client.get("/healthz")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_anonymous_requests_cannot_read_application_routes(self) -> None:
        with self.client() as client:
            page = client.get("/", follow_redirects=False)
            api = client.get("/api/private", follow_redirects=False)
            write = client.post("/logout")

        self.assertEqual(page.status_code, 303)
        self.assertEqual(page.headers["location"], "/login")
        self.assertEqual(api.status_code, 303)
        self.assertEqual(write.status_code, 401)

    def test_login_uses_openid_state_and_pkce(self) -> None:
        with self.client() as client:
            response = client.get("/login", follow_redirects=False)

        query = parse_qs(urlsplit(response.headers["location"]).query)
        self.assertEqual(query["scope"], ["openid"])
        self.assertEqual(query["code_challenge_method"], ["S256"])
        self.assertIn("state", query)
        self.assertIn("code_challenge", query)

    def test_both_allowed_identities_can_login(self) -> None:
        for subject in ("owner-sub", "buddy-sub"):
            with self.subTest(subject=subject), self.client(subject) as client:
                callback = complete_login(client, begin_login(client))
                page = client.get("/")

                self.assertEqual(callback.status_code, 303)
                self.assertEqual(page.status_code, 200)
                self.assertTrue(page.json()["authenticated"])

    def test_third_identity_is_forbidden(self) -> None:
        with self.client("third-sub") as client:
            response = complete_login(client, begin_login(client))

        self.assertEqual(response.status_code, 403)

    def test_oauth_denial_is_rejected(self) -> None:
        with self.client() as client:
            begin_login(client)
            response = client.get(
                "/auth/callback",
                params={"error": "access_denied"},
                follow_redirects=False,
            )

        self.assertEqual(response.status_code, 401)

    def test_state_mismatch_is_rejected(self) -> None:
        with self.client() as client:
            begin_login(client)
            response = complete_login(client, "wrong-state")

        self.assertEqual(response.status_code, 400)

    def test_token_exchange_failure_is_rejected(self) -> None:
        with self.client(fails=True) as client:
            response = complete_login(client, begin_login(client))

        self.assertEqual(response.status_code, 502)

    def test_session_cookie_has_required_flags(self) -> None:
        with self.client() as client:
            response = complete_login(client, begin_login(client))

        cookie = response.headers["set-cookie"].lower()
        self.assertIn("httponly", cookie)
        self.assertIn("secure", cookie)
        self.assertIn("samesite=lax", cookie)
        self.assertIn("max-age=28800", cookie)

    def test_logout_requires_csrf_token(self) -> None:
        with self.client() as client:
            complete_login(client, begin_login(client))
            token = client.get("/").json()["csrf_token"]
            rejected = client.post("/logout")
            accepted = client.post("/logout", headers={"X-CSRF-Token": token})
            page = client.get("/", follow_redirects=False)

        self.assertEqual(rejected.status_code, 403)
        self.assertEqual(accepted.status_code, 204)
        self.assertEqual(page.status_code, 303)

    def test_expired_session_is_rejected(self) -> None:
        session = {"user_sub": "owner-sub", "csrf_token": "token"}
        data = base64.b64encode(json.dumps(session).encode())
        signer = TimestampSigner(SESSION_SECRET)
        with patch.object(signer, "get_timestamp", return_value=1):
            cookie = signer.sign(data).decode()

        with self.client() as client:
            client.cookies.set("money_tree_session", cookie)
            response = client.get("/", follow_redirects=False)

        self.assertEqual(response.status_code, 303)

    def test_anonymous_websocket_is_rejected(self) -> None:
        with self.client() as client:
            with self.assertRaises(WebSocketDisconnect) as caught:
                with client.websocket_connect("/ws"):
                    pass

        self.assertEqual(caught.exception.code, 4401)


class WebConfigurationTest(unittest.TestCase):
    def test_callback_must_match_application_url(self) -> None:
        with self.assertRaises(ValueError):
            settings(railway_oauth_redirect_uri="https://other.test/auth/callback")

    def test_allowlist_requires_two_unique_subjects(self) -> None:
        with self.assertRaises(ValueError):
            settings(allowed_railway_subs="owner-sub,owner-sub")


if __name__ == "__main__":
    unittest.main()
