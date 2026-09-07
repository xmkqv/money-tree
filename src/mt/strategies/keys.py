from typing import Annotated, Literal, TypeIs, get_args

from pydantic import AfterValidator, BeforeValidator, Field, TypeAdapter


type StrategyKey = Literal["breakout_5m", "breakout_10m", "daily_sma", "daily_tfb"]
type Unattributed = Literal["unattributed"]

UNATTRIBUTED: Unattributed = "unattributed"

STRATEGY_KEYS: tuple[StrategyKey, ...] = get_args(StrategyKey.__value__)


def is_strategy_key(value: str) -> TypeIs[StrategyKey]:
    return value in STRATEGY_KEYS


def split_keys(value: object) -> object:
    if not isinstance(value, str):
        return value
    return [item.strip() for item in value.split(",") if item.strip()]


def check_distinct(values: tuple[StrategyKey, ...]) -> tuple[StrategyKey, ...]:
    if len(set(values)) != len(values):
        raise ValueError(f"strategy keys must be distinct, from: {', '.join(STRATEGY_KEYS)}")
    return values


type StrategySelection = Annotated[
    tuple[StrategyKey, ...],
    BeforeValidator(split_keys),
    AfterValidator(check_distinct),
    Field(min_length=1),
]

strategy_selection_adapter: TypeAdapter[tuple[StrategyKey, ...]] = TypeAdapter(StrategySelection)
