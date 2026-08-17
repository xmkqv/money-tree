from typing import Annotated, Self

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


type RequiredSecret = Annotated[SecretStr, Field(min_length=1)]
type SigningSecret = Annotated[SecretStr, Field(min_length=32)]


class WebSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", frozen=True
    )

    app_base_url: AnyHttpUrl
    railway_oauth_client_id: str = Field(min_length=1)
    railway_oauth_client_secret: RequiredSecret
    railway_oauth_redirect_uri: AnyHttpUrl
    allowed_railway_emails: Annotated[frozenset[str], NoDecode, Field(min_length=1)]
    session_secret: SigningSecret
    session_ttl_seconds: int = Field(default=28_800, gt=0, le=86_400)
    alpaca_is_paper: bool = True
    alpaca_api_key: RequiredSecret
    alpaca_api_secret: RequiredSecret
    state_export_secret: SigningSecret

    @field_validator("allowed_railway_emails", mode="before")
    def split_emails(cls, value: str) -> frozenset[str]:
        return frozenset(email.strip().casefold() for email in value.split(",") if email.strip())

    @model_validator(mode="after")
    def validate_web_configuration(self) -> Self:
        callback = f"{str(self.app_base_url).rstrip('/')}/auth/callback"
        if str(self.railway_oauth_redirect_uri) != callback:
            raise ValueError("RAILWAY_OAUTH_REDIRECT_URI must match APP_BASE_URL/auth/callback")
        return self
