from datetime import date
from typing import Annotated, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


type RiskLimit = Annotated[float, Field(gt=0, le=1)]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    strategy: str = "readme"
    backtest_start: date = date(2023, 1, 1)
    backtest_end: date = date(2024, 1, 1)
    alpaca_api_key: SecretStr | None = None
    alpaca_api_secret: SecretStr | None = None
    alpaca_is_paper: bool = True
    risk_per_day_max: RiskLimit = 0.02
    risk_per_trade_max: RiskLimit = 0.005

    @model_validator(mode="after")
    def validate_limits(self) -> Self:
        if self.risk_per_trade_max > self.risk_per_day_max:
            raise ValueError("risk per trade must not exceed risk per day")
        return self

    @property
    def risk_parameters(self) -> dict[str, float]:
        return {
            "risk_per_day_max": self.risk_per_day_max,
            "risk_per_trade_max": self.risk_per_trade_max,
        }


settings = Settings()
