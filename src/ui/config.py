from typing import Annotated, Literal, Self

from pydantic import AnyHttpUrl, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from bot.types import BrokerMode, RequiredSecret, RiskLimit, SigningSecret, TradingConfiguration


type Mode = Literal["development", "production"]


class WebSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", frozen=True)

    mode: Annotated[Mode, Field(validation_alias="MISE_ENV")]
    app_base_url: AnyHttpUrl
    session_secret: SigningSecret
    session_ttl_seconds: int = Field(gt=0, le=86_400)
    broker_mode: BrokerMode
    alpaca_api_key: RequiredSecret
    alpaca_api_secret: RequiredSecret
    fractional_orders: bool
    position_fraction_max: RiskLimit
    risk_per_day_max: RiskLimit
    risk_per_trade_max: RiskLimit
    state_export_secret: SigningSecret

    @model_validator(mode="after")
    def validate_web_configuration(self) -> Self:
        if self.risk_per_trade_max > self.risk_per_day_max:
            raise ValueError("risk per trade must not exceed risk per day")
        return self

    @property
    def railway_oauth_redirect_uri(self) -> str:
        return f"{str(self.app_base_url).rstrip('/')}/auth/callback"

    @property
    def trading_configuration(self) -> TradingConfiguration:
        return TradingConfiguration(
            fractional_orders=self.fractional_orders,
            position_fraction_max=self.position_fraction_max,
            risk_per_day_max=self.risk_per_day_max,
            risk_per_trade_max=self.risk_per_trade_max,
        )


class RailwayOAuthSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", frozen=True)

    railway_oauth_client_id: str = Field(min_length=1)
    railway_oauth_client_secret: RequiredSecret
    allowed_railway_emails: Annotated[frozenset[str], NoDecode, Field(min_length=1)]

    @field_validator("allowed_railway_emails", mode="before")
    def split_emails(cls, value: str) -> frozenset[str]:
        return frozenset(email.strip().casefold() for email in value.split(",") if email.strip())
