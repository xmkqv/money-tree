from collections.abc import Callable
from datetime import datetime
from typing import TypedDict, cast, get_args

from pydantic.fields import FieldInfo

from mt.config.settings import RuleSettings
from mt.config.values import UNATTRIBUTED, SettingsSection, StrategyKey, Unattributed
from mt.exchange import TRADING_ZONE, upcoming_session_bounds
from mt.strategies.base import Strategy
from mt.strategies.breakout import Breakout
from mt.strategies.order_tag import ORDER_TAG_PREFIX
from mt.strategies.registry import STRATEGIES


KINDS = {"breakout": "Intraday breakout", "daily": "Daily trend"}
ACRONYMS = {"atr": "ATR", "adx": "ADX", "rsi": "RSI", "sma": "SMA", "tfb": "TFB"}
BOUNDS = {"max": "≤", "min": "≥"}
UNITS = {
    "minutes": "min",
    "seconds": "s",
    "sessions": "sess",
    "days": "days",
    "bars": "bars",
    "multiple": "×",
    "multiples": "×",
    "fraction": "",
    "fractions": "",
}
FRACTIONS = {"Fraction", "OptionalFraction"}
NUMBERS = {"Count", "Amount", "int", "float"}
TEXTS = {"Symbol", "str"}
FLAGS = {"bool"}
STATE_FIELDS = {"is_paused"}
MARKET_CARD = "Market"


class ConfigRow(TypedDict):
    label: str
    bound: str
    value: str
    name: str


class ConfigCard(TypedDict):
    key: str
    name: str
    namespace: str
    rows: list[ConfigRow]


class StrategyConfig(TypedDict):
    cards: list[ConfigCard]
    configured: bool


class StrategyLabel(TypedDict):
    key: StrategyKey | Unattributed
    short: str
    label: str


EntryWindow = TypedDict("EntryWindow", {"from": str, "to": str})


def entry_windows(configuration: RuleSettings) -> dict[StrategyKey, EntryWindow]:
    opens, closes = upcoming_session_bounds(datetime.now(TRADING_ZONE).date())
    return {
        cls.key: _window(*_described(cls, configuration).entry_window(opens, closes))
        for cls in STRATEGIES
    }


def strategy_labels() -> list[StrategyLabel]:
    labels = [
        StrategyLabel(key=cls.key, short=cls.name(), label=f"{cls.name()} · {KINDS[cls.family]}")
        for cls in STRATEGIES
    ]
    labels.append(
        StrategyLabel(
            key=UNATTRIBUTED, short="Unattributed", label=f"No {ORDER_TAG_PREFIX}- order tag"
        )
    )
    return labels


def strategy_config(configuration: RuleSettings, *, configured: bool) -> StrategyConfig:
    scalars = [
        _row("", name, info, getattr(configuration, name))
        for name, info in RuleSettings.model_fields.items()
        if not _is_section(info)
    ]
    sections = [
        _card(name, getattr(configuration, name))
        for name, info in RuleSettings.model_fields.items()
        if _is_section(info)
    ]
    market = ConfigCard(key="", name=MARKET_CARD, namespace="", rows=scalars)
    return StrategyConfig(cards=[market, *sections], configured=configured)


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
    named = {cls.key: cls.name() for cls in STRATEGIES}
    if key in named:
        return named[key]
    if key in KINDS:
        return f"{key.capitalize()} family"
    return key.capitalize()


def _row(namespace: str, name: str, info: FieldInfo, value: object) -> ConfigRow:
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
    return ConfigRow(
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
    raise ValueError(f"{names} has no configuration card figure")


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
    return f"${figure / 1_000_000:g}M" if figure >= 1_000_000 else f"${figure:g}"


def _described(cls: type[Strategy], configuration: RuleSettings) -> type[Strategy]:
    described = cast(type[Strategy], type(cls.__name__, (cls,), {}))
    described.bind(getattr(configuration, cls.key))
    if issubclass(described, Breakout):
        described.bind(configuration.breakout)
    return described


def _window(opens: datetime, closes: datetime) -> EntryWindow:
    return EntryWindow({"from": f"{opens:%H:%M}", "to": f"{closes:%H:%M}"})
