from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Annotated, Literal, Self

from pandas import Series
from pydantic import (
    UUID4,
    AnyHttpUrl,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


type RiskLimit = Annotated[float, Field(gt=0, le=1)]
type SigningSecret = Annotated[SecretStr, Field(min_length=32)]
type RunStatus = Literal["starting", "running", "stopped", "failed"]
type EventLevel = Literal["info", "warning", "error"]
type ChartName = Literal["equity", "drawdown", "monthly", "trades"]
type ReportRow = list[str]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", frozen=True
    )

    strategy: str = "noop"
    backtest_start: datetime = datetime(2023, 1, 1)
    backtest_end: datetime = datetime(2024, 1, 1)
    alpaca_api_key: SecretStr | None = None
    alpaca_api_secret: SecretStr | None = None
    alpaca_is_paper: bool = True
    state_export_url: AnyHttpUrl | None = None
    state_export_secret: SigningSecret | None = None
    risk_per_day_max: RiskLimit = 0.02
    risk_per_trade_max: RiskLimit = 0.005
    position_fraction_max: RiskLimit = 0.20

    @model_validator(mode="after")
    def validate_limits(self) -> Self:
        if self.risk_per_trade_max > self.risk_per_day_max:
            raise ValueError("risk per trade must not exceed risk per day")
        if (self.state_export_url is None) != (self.state_export_secret is None):
            raise ValueError("state export URL and secret must be set together")
        return self

    @property
    def risk_parameters(self) -> dict[str, float]:
        return {
            "position_fraction_max": self.position_fraction_max,
            "risk_per_day_max": self.risk_per_day_max,
            "risk_per_trade_max": self.risk_per_trade_max,
        }


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class RuntimeEvent(_StrictModel):
    kind: str = Field(min_length=1, max_length=100)
    occurred_at: AwareDatetime
    level: EventLevel
    message: str = Field(min_length=1, max_length=500)


class RuntimeSnapshot(_StrictModel):
    run_id: UUID4
    sequence: int = Field(ge=1)
    status: RunStatus
    strategy: str = Field(min_length=1, max_length=100)
    started_at: AwareDatetime
    heartbeat_at: AwareDatetime
    events: list[RuntimeEvent] = Field(max_length=50)


class RunSettings(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    budget: float | None = None
    benchmark_asset: str | dict[str, object] | None = None
    lumibot_version: str | None = None
    parameters: dict[str, object] = Field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Fill:
    symbol: str
    sign: int
    quantity: float
    price: float
    filled_at: datetime


@dataclass(frozen=True, slots=True)
class RoundTrip:
    symbol: str
    sign: int
    quantity: float
    entry_at: datetime
    exit_at: datetime
    entry_price: float
    exit_price: float

    @property
    def pnl_usd(self) -> float:
        return self.sign * (self.exit_price - self.entry_price) * self.quantity

    @property
    def return_fraction(self) -> float:
        return self.sign * (self.exit_price / self.entry_price - 1.0)

    @property
    def holding_days(self) -> float:
        return (self.exit_at - self.entry_at) / timedelta(days=1)


@dataclass(frozen=True, slots=True)
class TradeStats:
    count: int
    win_rate: float | None
    profit_factor: float | None
    average_win: float | None
    average_loss: float | None
    best: float | None
    worst: float | None
    average_days: float | None


@dataclass(frozen=True, slots=True)
class ReportData:
    equity: Series
    returns: Series
    trips: list[RoundTrip]
    settings: RunSettings
    analytics: Mapping[str, object]
    trades: TradeStats
    scalars: dict[str, object]


class SectionModel(_StrictModel):
    heading: str


class TableSection(SectionModel):
    table: list[ReportRow]


class ImageSection(SectionModel):
    image: str
    caption: str


class BulletSection(SectionModel):
    bullets: list[str]


type Section = TableSection | ImageSection | BulletSection


class Report(_StrictModel):
    title: str
    summary: str
    sections: list[Section]
    footer: str
