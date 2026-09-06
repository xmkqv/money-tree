from typing import Literal, TypeIs, get_args


type StrategyName = Literal["breakout_5m", "breakout_10m", "daily_sma", "daily_tfb"]
type Unattributed = Literal["unattributed"]

UNATTRIBUTED: Unattributed = "unattributed"

STRATEGY_KEYS: tuple[StrategyName, ...] = get_args(StrategyName.__value__)


def is_strategy_name(value: str) -> TypeIs[StrategyName]:
    return value in STRATEGY_KEYS
