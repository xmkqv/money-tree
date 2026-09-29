from collections.abc import Mapping
from typing import Protocol, cast

from authlib.integrations.starlette_client import OAuth
from pydantic import BaseModel, ConfigDict, Field
from starlette.requests import Request
from starlette.responses import Response

from mt.rules.sections import LoginSection
from mt.rules.values import Email

from .http import http_timeout


METADATA_URL = "https://backboard.railway.com/oauth/.well-known/openid-configuration"


class Identity(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True, str_strip_whitespace=True)

    sub: str = Field(min_length=1)
    email: Email


class RailwayOAuth(Protocol):
    async def authorize_redirect(self, request: Request, redirect_uri: str) -> Response: ...

    async def authorize_access_token(self, request: Request) -> Mapping[str, object]: ...

    async def userinfo(self, *, token: Mapping[str, object]) -> Mapping[str, object]: ...


def railway_oauth(login: LoginSection) -> RailwayOAuth:
    return cast(
        RailwayOAuth,
        OAuth().register(  # pyright: ignore[reportUnknownMemberType]
            "railway",
            client_id=login.oauth_client_id,
            client_secret=login.oauth_client_secret.get_secret_value(),
            server_metadata_url=METADATA_URL,
            client_kwargs={
                "scope": "openid email",
                "code_challenge_method": "S256",
                "timeout": http_timeout(login.timeout),
            },
        ),
    )
