from typing import Annotated, Literal, TypeIs, get_args

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    SecretStr,
    TypeAdapter,
)


type StrategyKey = Literal["breakout_5m", "breakout_10m", "daily_sma", "daily_tfb"]

STRATEGY_KEYS: tuple[StrategyKey, ...] = get_args(StrategyKey.__value__)


def parse_none(value: object) -> object:
    return None if value == "none" else value


def split_keys(value: object) -> object:
    if not isinstance(value, str):
        return value
    return [item.strip() for item in value.split(",") if item.strip()]


def check_distinct(values: tuple[StrategyKey, ...]) -> tuple[StrategyKey, ...]:
    if len(set(values)) != len(values):
        raise ValueError(f"strategy keys must be distinct; choose from: {', '.join(STRATEGY_KEYS)}")
    return values


def is_strategy_key(value: str) -> TypeIs[StrategyKey]:
    return value in STRATEGY_KEYS


type Count = Annotated[int, Field(gt=0)]
type Amount = Annotated[float, Field(gt=0)]
type Fraction = Annotated[float, Field(gt=0, le=1)]
type OptionalFraction = Annotated[Fraction | None, BeforeValidator(parse_none)]
type MaxAge = Annotated[int, Field(ge=0)]
type Symbol = Annotated[str, Field(min_length=1, max_length=12, pattern=r"^[A-Z][A-Z.]*$")]
type CssToken = Annotated[str, Field(pattern=r"^--[a-z0-9-]+$")]
type RequiredSecret = Annotated[SecretStr, Field(min_length=1)]
type SigningSecret = Annotated[SecretStr, Field(min_length=32)]
type Mode = Literal["development", "production"]
type BrokerMode = Literal["live", "paper"]
type DataFeedName = Literal["sip", "delayed_sip", "iex"]
type Timeframe = Annotated[str, Field(pattern=r"^\d+(Min|Hour|Day)$")]
type EquityPeriod = Annotated[str, Field(pattern=r"^\d+[DWMA]$")]
type EquityTimeframe = Annotated[str, Field(pattern=r"^\d+(Min|H|D)$")]
type ChartTimeframe = Literal["5Min", "1Hour", "1Day"]
type StrategySelection = Annotated[
    tuple[StrategyKey, ...],
    BeforeValidator(split_keys),
    AfterValidator(check_distinct),
    Field(min_length=1),
]

CHART_TIMEFRAMES: tuple[ChartTimeframe, ...] = get_args(ChartTimeframe.__value__)

strategy_selection_adapter: TypeAdapter[tuple[StrategyKey, ...]] = TypeAdapter(StrategySelection)


class SettingsSection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
