from types import TracebackType
from typing import Annotated, NamedTuple, Protocol, Self, cast

import httpx2
from authlib.common.security import generate_token
from authlib.integrations.httpx_client import AsyncOAuth2Client
from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from mt.rules.sections import LoginSection

from .http import http_timeout


AUTHORIZATION_URL = "https://backboard.railway.com/oauth/auth"
TOKEN_URL = "https://backboard.railway.com/oauth/token"
IDENTITY_URL = "https://backboard.railway.com/oauth/me"


class AuthorizationRequest(NamedTuple):
    url: str
    state: str
    verifier: str


class Identity(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True, str_strip_whitespace=True)

    sub: str = Field(min_length=1)
    email: Annotated[str, AfterValidator(str.casefold)] = Field(min_length=1)


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

    async def get(self, url: str) -> httpx2.Response: ...


class RailwayOAuthClient:
    def __init__(self, login: LoginSection, redirect_uri: str) -> None:
        self._login = login
        self._redirect_uri = redirect_uri

    def _client(self) -> _OAuthClient:
        return cast(
            _OAuthClient,
            AsyncOAuth2Client(
                self._login.oauth_client_id,
                self._login.oauth_client_secret.get_secret_value(),
                scope="openid email",
                redirect_uri=self._redirect_uri,
                code_challenge_method="S256",
                timeout=http_timeout(self._login.timeout),
            ),
        )

    async def authorization_request(self) -> AuthorizationRequest:
        verifier = generate_token(64)
        async with self._client() as client:
            url, state = client.create_authorization_url(AUTHORIZATION_URL, code_verifier=verifier)
        return AuthorizationRequest(url, state, verifier)

    async def identify(self, code: str, verifier: str) -> Identity:
        async with self._client() as client:
            await client.fetch_token(TOKEN_URL, code=code, code_verifier=verifier)
            identity = await client.get(IDENTITY_URL)
            identity.raise_for_status()
            return Identity.model_validate_json(identity.content)
