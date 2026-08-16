from functools import cached_property
from typing import Annotated, Self

from pydantic import AnyHttpUrl, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


type RequiredSecret = Annotated[SecretStr, Field(min_length=1)]
type SigningSecret = Annotated[SecretStr, Field(min_length=32)]


class WebSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    app_base_url: AnyHttpUrl
    railway_oauth_client_id: str = Field(min_length=1)
    railway_oauth_client_secret: RequiredSecret
    railway_oauth_redirect_uri: AnyHttpUrl
    allowed_railway_subs: str = Field(min_length=1)
    session_secret: SigningSecret
    session_ttl_seconds: int = Field(default=28_800, gt=0, le=86_400)
    alpaca_api_key: RequiredSecret
    alpaca_api_secret: RequiredSecret
    state_export_secret: SigningSecret

    @cached_property
    def allowed_subjects(self) -> frozenset[str]:
        return frozenset(
            subject.strip()
            for subject in self.allowed_railway_subs.split(",")
            if subject.strip()
        )

    @model_validator(mode="after")
    def validate_web_configuration(self) -> Self:
        callback = f"{str(self.app_base_url).rstrip('/')}/auth/callback"
        if str(self.railway_oauth_redirect_uri) != callback:
            raise ValueError("RAILWAY_OAUTH_REDIRECT_URI must match APP_BASE_URL/auth/callback")
        if not self.allowed_subjects:
            raise ValueError(
                "ALLOWED_RAILWAY_SUBS must contain at least one subject"
            )
        return self
