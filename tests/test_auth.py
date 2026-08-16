import unittest
from unittest.mock import Mock, patch

import httpx

from ui.auth import IDENTITY_URL, TOKEN_URL, RailwayIdentityError, RailwayOAuthClient
from ui.config import WebSettings


def settings() -> WebSettings:
    return WebSettings(
        app_base_url="https://testserver",
        railway_oauth_client_id="client-id",
        railway_oauth_client_secret="client-secret",
        railway_oauth_redirect_uri="https://testserver/auth/callback",
        allowed_railway_subs="owner-sub,buddy-sub",
        session_secret="0123456789abcdef0123456789abcdef",
    )


class IdentityResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, str]:
        return {"sub": "owner-sub"}


class OAuthSession:
    def __init__(self, fails: bool = False) -> None:
        self.fails = fails
        self.fetch_call: tuple[str, str, str] | None = None
        self.identity_url: str | None = None

    async def __aenter__(self) -> "OAuthSession":
        return self

    async def __aexit__(self, *arguments: object) -> None:
        return None

    async def fetch_token(self, url: str, code: str, code_verifier: str) -> None:
        if self.fails:
            raise httpx.ConnectError("test failure")
        self.fetch_call = (url, code, code_verifier)

    async def get(self, url: str) -> IdentityResponse:
        self.identity_url = url
        return IdentityResponse()


class RailwayOAuthClientTest(unittest.IsolatedAsyncioTestCase):
    async def test_identity_lookup_uses_basic_auth_and_pkce(self) -> None:
        session = OAuthSession()
        session_type = Mock(return_value=session)
        client = RailwayOAuthClient(settings())

        with patch("ui.auth.AsyncOAuth2Client", session_type):
            subject = await client.identify("code", "verifier")

        self.assertEqual(subject, "owner-sub")
        self.assertEqual(session.fetch_call, (TOKEN_URL, "code", "verifier"))
        self.assertEqual(session.identity_url, IDENTITY_URL)
        self.assertEqual(
            session_type.call_args.kwargs["token_endpoint_auth_method"],
            "client_secret_basic",
        )

    async def test_identity_lookup_wraps_token_failure(self) -> None:
        session_type = Mock(return_value=OAuthSession(fails=True))
        client = RailwayOAuthClient(settings())

        with patch("ui.auth.AsyncOAuth2Client", session_type):
            with self.assertRaises(RailwayIdentityError):
                await client.identify("code", "verifier")


if __name__ == "__main__":
    unittest.main()
