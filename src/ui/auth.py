import base64
import hashlib
import secrets
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from ui.config import WebSettings


AUTHORIZATION_URL = "https://backboard.railway.com/oauth/auth"
TOKEN_URL = "https://backboard.railway.com/oauth/token"
IDENTITY_URL = "https://backboard.railway.com/oauth/me"


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
        configuration = self._configuration
        async with httpx.AsyncClient(timeout=10) as client:
            token = await client.post(
                TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "code_verifier": verifier,
                    "redirect_uri": str(configuration.railway_oauth_redirect_uri),
                },
                auth=(
                    configuration.railway_oauth_client_id,
                    configuration.railway_oauth_client_secret.get_secret_value(),
                ),
            )
            token.raise_for_status()
            identity = await client.get(
                IDENTITY_URL,
                headers={"Authorization": f"Bearer {token.json()['access_token']}"},
            )
            identity.raise_for_status()
            subject = identity.json()["sub"]
        if not isinstance(subject, str) or not subject:
            raise ValueError("Railway OAuth identity did not contain a subject")
        return subject
