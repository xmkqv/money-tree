from types import TracebackType
from typing import NamedTuple, Protocol, Self, cast

import httpx
from authlib.common.security import generate_token
from authlib.integrations.httpx_client import AsyncOAuth2Client
from pydantic import TypeAdapter

from .config import WebSettings


AUTHORIZATION_URL = "https://backboard.railway.com/oauth/auth"
TOKEN_URL = "https://backboard.railway.com/oauth/token"
IDENTITY_URL = "https://backboard.railway.com/oauth/me"


class AuthorizationRequest(NamedTuple):
    url: str
    state: str
    verifier: str


class RailwayIdentity(NamedTuple):
    subject: str
    email: str


class _OAuthClient(Protocol):
    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def create_authorization_url(self, url: str, *, code_verifier: str) -> tuple[str, str]: ...

    async def fetch_token(self, url: str, *, code: str, code_verifier: str) -> object: ...

    async def get(self, url: str) -> httpx.Response: ...


class RailwayOAuthClient:
    def __init__(self, configuration: WebSettings) -> None:
        self._configuration = configuration

    def _client(self) -> _OAuthClient:
        configuration = self._configuration
        return cast(
            _OAuthClient,
            AsyncOAuth2Client(
                configuration.railway_oauth_client_id,
                configuration.railway_oauth_client_secret.get_secret_value(),
                scope="openid email",
                redirect_uri=str(configuration.railway_oauth_redirect_uri),
                code_challenge_method="S256",
                timeout=10,
            ),
        )

    async def authorization_request(self) -> AuthorizationRequest:
        verifier = generate_token(64)
        async with self._client() as client:
            url, state = client.create_authorization_url(AUTHORIZATION_URL, code_verifier=verifier)
        return AuthorizationRequest(url, state, verifier)

    async def identify(self, code: str, verifier: str) -> RailwayIdentity:
        async with self._client() as client:
            await client.fetch_token(TOKEN_URL, code=code, code_verifier=verifier)
            identity = await client.get(IDENTITY_URL)
            identity.raise_for_status()
            claims = TypeAdapter(dict[str, object]).validate_python(identity.json())
            subject = claims.get("sub")
            email = claims.get("email")
        if (
            not isinstance(subject, str)
            or not subject.strip()
            or not isinstance(email, str)
            or not email.strip()
        ):
            raise ValueError("Railway OAuth identity did not contain a subject and email")
        return RailwayIdentity(subject, email)
