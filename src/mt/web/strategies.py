from collections.abc import Callable
from datetime import datetime
from functools import cache
from typing import TypedDict, cast, get_args

from pydantic.fields import FieldInfo

from mt.exchange import today_on, upcoming_session_bounds
from mt.rules.settings import RuleSettings
from mt.rules.values import (
    UNATTRIBUTED,
    Amount,
    Count,
    Fraction,
    SettingsSection,
    StrategyKey,
    Symbol,
    Unattributed,
)
from mt.strategies.base import Strategy
from mt.strategies.breakout import Breakout
from mt.strategies.registry import ORDER_PREFIX, STRATEGIES


class FindFigureError(Exception):
    pass


class RuleRow(TypedDict):
    label: str
    bound: str
    value: str
    name: str


class ConfigCard(TypedDict):
    key: str
    name: str
    namespace: str
    rows: list[RuleRow]


class StrategyRules(TypedDict):
    cards: list[ConfigCard]
    isReported: bool


class StrategyLabel(TypedDict):
    key: StrategyKey | Unattributed
    short: str
    label: str


class EntryWindow(TypedDict):
    startAt: str
    endAt: str


FAMILIES = {
    "breakout": "Intraday breakout",
    "daily": "Daily trend",
}
ACRONYMS = {"atr": "ATR", "adx": "ADX", "rsi": "RSI"}
BOUNDS = {"max": "≤", "min": "≥"}
UNITS = {
    "minutes": "min",
    "hours": "h",
    "sessions": "sess",
    "days": "days",
    "bars": "bars",
    "multiple": "×",
    "multiples": "×",
    "fraction": "",
    "fractions": "",
}
FRACTIONS: set[object] = {Fraction}
NUMBERS: set[object] = {Count, Amount, int, float}
TEXTS: set[object] = {Symbol, str}
FLAGS: set[object] = {bool}
STATE_FIELDS = {"is_paused"}
MARKET_CARD = "Market"
STRATEGY_LABELS: list[StrategyLabel] = [
    StrategyLabel(key=cls.key, short=cls.name(), label=f"{cls.name()} · {FAMILIES[cls.family]}")
    for cls in STRATEGIES
] + [StrategyLabel(key=UNATTRIBUTED, short="Unattributed", label=f"No {ORDER_PREFIX}- order code")]
CARD_NAMES: dict[str, str] = {cls.key: cls.name() for cls in STRATEGIES}


def entry_windows(rules: RuleSettings) -> dict[StrategyKey, EntryWindow]:
    opens_at, closes_at = upcoming_session_bounds(today_on())
    return {
        cls.key: _window(*describe_strategy(cls, rules).entry_window(opens_at, closes_at))
        for cls in STRATEGIES
    }


def strategy_rules(rules: RuleSettings, *, is_reported: bool) -> StrategyRules:
    scalars = [
        _row("", name, info, getattr(rules, name))
        for name, info in RuleSettings.model_fields.items()
        if not _is_section(info)
    ]
    sections = [
        _card(name, getattr(rules, name))
        for name, info in RuleSettings.model_fields.items()
        if _is_section(info)
    ]
    market = ConfigCard(key="", name=MARKET_CARD, namespace="", rows=scalars)
    return StrategyRules(cards=[market, *sections], isReported=is_reported)


def describe_strategy[Described: Strategy](
    strategy: type[Described], rules: RuleSettings
) -> type[Described]:
    return cast(type[Described], _described(strategy, rules))  # pyright: ignore[reportArgumentType]


@cache
def _described(strategy: type[Strategy], rules: RuleSettings) -> type[Strategy]:
    attributes: dict[str, object] = {"rules": getattr(rules, strategy.key)}
    if issubclass(strategy, Breakout):
        attributes["family_rules"] = rules.breakout
    return cast(type[Strategy], type(strategy.__name__, (strategy,), attributes))


def _is_section(info: FieldInfo) -> bool:
    return isinstance(info.annotation, type) and issubclass(info.annotation, SettingsSection)


def _card(key: str, section: SettingsSection) -> ConfigCard:
    namespace = f"{key.upper()}__"
    return ConfigCard(
        key=key,
        name=_card_name(key),
        namespace=namespace,
        rows=[
            _row(namespace, name, info, getattr(section, name))
            for name, info in type(section).model_fields.items()
            if name not in STATE_FIELDS
        ],
    )


def _card_name(key: str) -> str:
    if key in CARD_NAMES:
        return CARD_NAMES[key]
    if key in FAMILIES:
        return f"{key.capitalize()} family"
    return key.capitalize()


def _row(namespace: str, name: str, info: FieldInfo, value: object) -> RuleRow:
    words = name.split("_")
    if words[0] in {"is", "does"}:
        words = words[1:]
    bound = BOUNDS.get(words[-1], "")
    if bound:
        words = words[:-1]
    unit = next((UNITS[word] for word in words if word in UNITS), "")
    words = [word for word in words if word not in UNITS]
    is_money = "usd" in words
    words = [word for word in words if word != "usd"]
    return RuleRow(
        label=" ".join(ACRONYMS.get(word, word) for word in words),
        bound="" if value is None else bound,
        value=_value(info, value, unit=unit, is_money=is_money),
        name=f"{namespace}{name.upper()}",
    )


def _value(info: FieldInfo, value: object, *, unit: str, is_money: bool) -> str:
    if value is None:
        return "—"
    figures = _figure(info.annotation, is_money=is_money)(_parts(value))
    return f"{figures} {unit}" if unit.isalpha() else f"{figures}{unit}"


def _parts(value: object) -> tuple[object, ...]:
    return cast(tuple[object, ...], value) if isinstance(value, tuple) else (value,)


def _figure(annotation: object, *, is_money: bool) -> Callable[[tuple[object, ...]], str]:
    parts: set[object] = set(get_args(annotation) or (annotation,))
    if parts & FRACTIONS:
        return _joined(_percent)
    if parts & NUMBERS:
        return _joined(_money if is_money else _number)
    if parts & TEXTS:
        return _joined(str)
    if parts & FLAGS:
        return _joined(_flag)
    raise FindFigureError(f"{parts} has no config card figure")


def _joined(figure: Callable[[object], str]) -> Callable[[tuple[object, ...]], str]:
    return lambda parts: " / ".join(figure(part) for part in parts)


def _flag(value: object) -> str:
    return "yes" if value else "no"


def _percent(value: object) -> str:
    return f"{cast(float, value) * 100:.2f}".rstrip("0").rstrip(".") + "%"


def _number(value: object) -> str:
    return f"{cast(float, value):g}"


def _money(value: object) -> str:
    figure = cast(float, value)
    if figure >= 1_000_000_000:
        return f"${figure / 1_000_000_000:g}B"
    return f"${figure / 1_000_000:g}M" if figure >= 1_000_000 else f"${figure:g}"


def _window(start_at: datetime, end_at: datetime) -> EntryWindow:
    return EntryWindow(startAt=start_at.isoformat(), endAt=end_at.isoformat())
