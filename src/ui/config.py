from typing import Annotated, Literal

from pydantic import AfterValidator, AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from bot.types import (
    BrokerSection,
    ExportSection,
    RequiredSecret,
    RiskSection,
    SettingsSection,
    SigningSecret,
    Symbol,
)


type Mode = Literal["development", "production"]
type Count = Annotated[int, Field(gt=0)]
type MaxAge = Annotated[int, Field(ge=0)]


class WebSection(SettingsSection):
    base_url: AnyHttpUrl
    session_secret: SigningSecret
    session_ttl_seconds: Annotated[int, Field(gt=0, le=86_400)]
    heartbeat_timeout_seconds: Count
    signature_window_seconds: Count
    state_body_bytes_max: Count


class DashboardSection(SettingsSection):
    ledger_ttl_seconds: Count
    pulse_ttl_seconds: Count
    chart_ttl_seconds: Count
    chart_cache_max: Count
    levels_history_days: Count
    session_source_bars_max: Count
    session_source_pages_max: Count
    page_rows_max: Count
    pages_max: Count
    sma_lengths: tuple[int, ...] = Field(min_length=1)
    ledger_max_age_seconds: MaxAge
    chart_max_age_seconds: MaxAge
    levels_max_age_seconds: MaxAge
    strategies_max_age_seconds: MaxAge
    refresh_poll_seconds: Count
    pulse_poll_seconds: Count


class LoginSection(SettingsSection):
    railway_oauth_client_id: str = Field(min_length=1)
    railway_oauth_client_secret: RequiredSecret
    allowed_railway_emails: frozenset[Annotated[str, AfterValidator(str.casefold)]] = Field(
        min_length=1
    )


class WebSettings(BaseSettings):
    model_config = SettingsConfigDict(env_nested_delimiter="__", extra="ignore", frozen=True)

    mode: Annotated[Mode, Field(validation_alias="MISE_ENV")]
    benchmark_symbol: Symbol
    broker: BrokerSection
    risk: RiskSection
    export: ExportSection
    web: WebSection
    dashboard: DashboardSection

    @property
    def railway_oauth_redirect_uri(self) -> str:
        return f"{str(self.web.base_url).rstrip('/')}/auth/callback"


class LoginSettings(BaseSettings):
    model_config = SettingsConfigDict(env_nested_delimiter="__", extra="ignore", frozen=True)

    login: LoginSection
