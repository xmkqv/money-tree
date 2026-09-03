from typing import Annotated, Self

from pydantic import AnyHttpUrl, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from bot.types import RequiredSecret, RiskLimit, SigningSecret, TradingConfiguration


class WebSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", frozen=True)

    app_base_url: AnyHttpUrl
    railway_oauth_client_id: str = Field(min_length=1)
    railway_oauth_client_secret: RequiredSecret
    railway_oauth_redirect_uri: AnyHttpUrl
    allowed_railway_emails: Annotated[frozenset[str], NoDecode, Field(min_length=1)]
    session_secret: SigningSecret
    session_ttl_seconds: int = Field(gt=0, le=86_400)
    alpaca_is_paper: bool
    alpaca_api_key: RequiredSecret
    alpaca_api_secret: RequiredSecret
    fractional_orders: bool
    position_fraction_max: RiskLimit
    risk_per_day_max: RiskLimit
    risk_per_trade_max: RiskLimit
    state_export_secret: SigningSecret

    @field_validator("allowed_railway_emails", mode="before")
    def split_emails(cls, value: str) -> frozenset[str]:
        return frozenset(email.strip().casefold() for email in value.split(",") if email.strip())

    @model_validator(mode="after")
    def validate_web_configuration(self) -> Self:
        callback = f"{str(self.app_base_url).rstrip('/')}/auth/callback"
        if str(self.railway_oauth_redirect_uri) != callback:
            raise ValueError("RAILWAY_OAUTH_REDIRECT_URI must match APP_BASE_URL/auth/callback")
        if self.risk_per_trade_max > self.risk_per_day_max:
            raise ValueError("risk per trade must not exceed risk per day")
        return self

    @property
    def trading_configuration(self) -> TradingConfiguration:
        return TradingConfiguration(
            fractional_orders=self.fractional_orders,
            position_fraction_max=self.position_fraction_max,
            risk_per_day_max=self.risk_per_day_max,
            risk_per_trade_max=self.risk_per_trade_max,
        )
