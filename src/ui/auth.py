from typing import NamedTuple

from authlib.common.security import generate_token
from authlib.integrations.httpx_client import AsyncOAuth2Client

from ui.config import WebSettings


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


class RailwayOAuthClient:
    def __init__(self, configuration: WebSettings) -> None:
        self._configuration = configuration

    def _client(self) -> AsyncOAuth2Client:
        configuration = self._configuration
        return AsyncOAuth2Client(
            configuration.railway_oauth_client_id,
            configuration.railway_oauth_client_secret.get_secret_value(),
            scope="openid email",
            redirect_uri=str(configuration.railway_oauth_redirect_uri),
            code_challenge_method="S256",
            timeout=10,
        )

    async def authorization_request(self) -> AuthorizationRequest:
        verifier = generate_token(64)
        async with self._client() as client:
            url, state = client.create_authorization_url(
                AUTHORIZATION_URL, code_verifier=verifier
            )
        return AuthorizationRequest(url, state, verifier)

    async def identify(self, code: str, verifier: str) -> RailwayIdentity:
        async with self._client() as client:
            await client.fetch_token(TOKEN_URL, code=code, code_verifier=verifier)
            identity = await client.get(IDENTITY_URL)
            identity.raise_for_status()
            claims = identity.json()
            subject, email = claims["sub"], claims["email"]
        if not isinstance(subject, str) or not subject or not isinstance(email, str) or not email:
            raise ValueError("Railway OAuth identity did not contain a subject and email")
        return RailwayIdentity(subject, email)
