import base64
import hashlib
import secrets
from dataclasses import dataclass
from typing import Any, Protocol, cast
from urllib.parse import urlencode

import httpx
from authlib.integrations.base_client.errors import OAuthError
from authlib.integrations.httpx_client import AsyncOAuth2Client

from ui.config import WebSettings


AUTHORIZATION_URL = "https://backboard.railway.com/oauth/auth"
TOKEN_URL = "https://backboard.railway.com/oauth/token"
IDENTITY_URL = "https://backboard.railway.com/oauth/me"


class RailwayIdentityError(RuntimeError):
    pass


class IdentityClient(Protocol):
    async def identify(self, code: str, verifier: str) -> str: ...


@dataclass(frozen=True, slots=True)
class AuthorizationRequest:
    url: str
    state: str
    verifier: str


class RailwayOAuthClient:
    def __init__(self, configuration: WebSettings) -> None:
        self._configuration = configuration

    def authorization_request(self) -> AuthorizationRequest:
        state = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        digest = hashlib.sha256(verifier.encode()).digest()
        challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
        query = urlencode(
            {
                "response_type": "code",
                "client_id": self._configuration.railway_oauth_client_id,
                "redirect_uri": str(self._configuration.railway_oauth_redirect_uri),
                "scope": "openid",
                "state": state,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
        )
        return AuthorizationRequest(
            url=f"{AUTHORIZATION_URL}?{query}",
            state=state,
            verifier=verifier,
        )

    async def identify(self, code: str, verifier: str) -> str:
        try:
            async with AsyncOAuth2Client(  # pyright: ignore[reportGeneralTypeIssues]
                client_id=self._configuration.railway_oauth_client_id,
                client_secret=self._configuration.railway_oauth_client_secret.get_secret_value(),
                redirect_uri=str(self._configuration.railway_oauth_redirect_uri),
                scope="openid",
                token_endpoint_auth_method="client_secret_basic",
            ) as oauth_client:  # pyright: ignore[reportUnknownVariableType]
                client = cast(httpx.AsyncClient, oauth_client)
                await cast(Any, client).fetch_token(
                    TOKEN_URL,
                    code=code,
                    code_verifier=verifier,
                )
                response = await client.get(IDENTITY_URL)
                response.raise_for_status()
                identity = response.json()
                if not isinstance(identity, dict):
                    raise RailwayIdentityError("Railway OAuth identity was invalid")
                subject = cast(dict[str, Any], identity).get("sub")
        except (OAuthError, httpx.HTTPError, TypeError, ValueError) as error:
            raise RailwayIdentityError("Railway OAuth identity lookup failed") from error
        if not isinstance(subject, str) or not subject:
            raise RailwayIdentityError("Railway OAuth identity did not contain a subject")
        return subject
