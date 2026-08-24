from bot.types import STRATEGY_LABELS, StrategyName


STRATEGY_CODES: dict[StrategyName, str] = {
    "noop": "n",
    "orb": "o",
    "sma": "s",
    "tfb_50": "t",
    "orb_momentum": "m",
}
STRATEGIES_BY_CODE: dict[str, StrategyName] = {
    code: strategy for strategy, code in STRATEGY_CODES.items()
}


def find_order_strategy(value: str) -> StrategyName | None:
    parts = value.split("-")
    if len(parts) != 6 or parts[0] != "mt":
        return None
    return STRATEGIES_BY_CODE.get(parts[1])


def find_order_strategy_label(value: str) -> str | None:
    strategy = find_order_strategy(value)
    return None if strategy is None else STRATEGY_LABELS[strategy]
