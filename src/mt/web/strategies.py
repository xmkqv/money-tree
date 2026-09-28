from collections.abc import Callable
from datetime import datetime
from typing import TypedDict, cast, get_args

from pydantic.fields import FieldInfo

from mt.exchange import today, upcoming_session_bounds
from mt.rules.settings import RuleSettings
from mt.rules.values import UNATTRIBUTED, SettingsSection, StrategyKey, Unattributed
from mt.strategies.base import Strategy
from mt.strategies.breakout import Breakout
from mt.strategies.registry import ORDER_PREFIX, STRATEGIES


FAMILIES = {
    "breakout": "Intraday breakout",
    "daily": "Daily trend",
    "intraday": "Intraday momentum",
    "allocation": "Asset allocation",
    "quality": "Monthly quality",
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
FRACTIONS = {"Fraction"}
NUMBERS = {"Count", "Amount", "int", "float"}
TEXTS = {"Symbol", "str"}
FLAGS = {"bool"}
STATE_FIELDS = {"is_paused"}
MARKET_CARD = "Market"


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
    reported: bool


class StrategyLabel(TypedDict):
    key: StrategyKey | Unattributed
    short: str
    label: str


EntryWindow = TypedDict("EntryWindow", {"from": str, "to": str})


def entry_windows(rules: RuleSettings) -> dict[StrategyKey, EntryWindow]:
    opens, closes = upcoming_session_bounds(today())
    return {
        cls.key: _window(*_described(cls, rules).entry_window(opens, closes)) for cls in STRATEGIES
    }


STRATEGY_LABELS: list[StrategyLabel] = [
    StrategyLabel(key=cls.key, short=cls.name(), label=f"{cls.name()} · {FAMILIES[cls.family]}")
    for cls in STRATEGIES
] + [StrategyLabel(key=UNATTRIBUTED, short="Unattributed", label=f"No {ORDER_PREFIX}- order code")]


def strategy_rules(rules: RuleSettings, *, reported: bool) -> StrategyRules:
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
    return StrategyRules(cards=[market, *sections], reported=reported)


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


CARD_NAMES: dict[str, str] = {cls.key: cls.name() for cls in STRATEGIES}


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
    money = "usd" in words
    words = [word for word in words if word != "usd"]
    return RuleRow(
        label=" ".join(ACRONYMS.get(word, word) for word in words),
        bound="" if value is None else bound,
        value=_value(info, value, unit=unit, money=money),
        name=f"{namespace}{name.upper()}",
    )


def _value(info: FieldInfo, value: object, *, unit: str, money: bool) -> str:
    if value is None:
        return "—"
    figures = _figure(info.annotation, money=money)(_parts(value))
    return f"{figures} {unit}" if unit.isalpha() else f"{figures}{unit}"


def _parts(value: object) -> tuple[object, ...]:
    return cast(tuple[object, ...], value) if isinstance(value, tuple) else (value,)


def _figure(annotation: object, *, money: bool) -> Callable[[tuple[object, ...]], str]:
    names = {getattr(part, "__name__", "") for part in get_args(annotation) or (annotation,)}
    if names & FRACTIONS:
        return _joined(_percent)
    if names & NUMBERS:
        return _joined(_money if money else _number)
    if names & TEXTS:
        return _joined(str)
    if names & FLAGS:
        return _joined(_flag)
    raise ValueError(f"{names} has no config card figure")


def _joined(figure: Callable[[object], str]) -> Callable[[tuple[object, ...]], str]:
    return lambda parts: " / ".join(figure(part) for part in parts)


def _flag(value: object) -> str:
    return "yes" if value else "no"


def _numeric(value: object) -> float:
    if not isinstance(value, int | float):
        raise TypeError(f"{value!r} is not a number")
    return float(value)


def _percent(value: object) -> str:
    return f"{_numeric(value) * 100:.2f}".rstrip("0").rstrip(".") + "%"


def _number(value: object) -> str:
    return f"{_numeric(value):g}"


def _money(value: object) -> str:
    figure = _numeric(value)
    if figure >= 1_000_000_000:
        return f"${figure / 1_000_000_000:g}B"
    return f"${figure / 1_000_000:g}M" if figure >= 1_000_000 else f"${figure:g}"


def _described(cls: type[Strategy], rules: RuleSettings) -> type[Strategy]:
    is_breakout = issubclass(cls, Breakout)
    attributes: dict[str, object] = {"rules": getattr(rules, cls.key)}
    if is_breakout:
        attributes["family_rules"] = rules.breakout
    return type(cls.__name__, (cls,), attributes)


def _window(opens: datetime, closes: datetime) -> EntryWindow:
    return EntryWindow({"from": f"{opens:%H:%M}", "to": f"{closes:%H:%M}"})
