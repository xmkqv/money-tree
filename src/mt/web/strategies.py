from datetime import datetime
from typing import TypedDict, cast

from mt.config.sections import RiskSection
from mt.config.settings import RuleSettings
from mt.exchange import TRADING_ZONE, upcoming_session_bounds
from mt.strategies.base import Strategy
from mt.strategies.breakout import Breakout
from mt.strategies.order_tag import ORDER_TAG_PREFIX, UNATTRIBUTED
from mt.strategies.registry import STRATEGIES

from .rules import KINDS, RULE_FIELDS, Row, percent, strategy_rows


class StrategyCard(TypedDict):
    key: str
    name: str
    kind: str
    rows: list[Row]


class StrategyLabel(TypedDict):
    key: str
    short: str
    label: str


class StrategyRules(TypedDict):
    fields: list[str]
    strategies: list[StrategyCard]
    portfolio: list[Row]
    configured: bool


EntryWindow = TypedDict("EntryWindow", {"from": str, "to": str})


def entry_windows(configuration: RuleSettings) -> dict[str, EntryWindow]:
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


def strategy_rules(configuration: RuleSettings, *, configured: bool) -> StrategyRules:
    opens, closes = upcoming_session_bounds(datetime.now(TRADING_ZONE).date())
    return StrategyRules(
        fields=list(RULE_FIELDS),
        strategies=[_card(cls, configuration, opens, closes) for cls in STRATEGIES],
        portfolio=portfolio_rules(configuration.risk, configuration.breakout.positions_max),
        configured=configured,
    )


def portfolio_rules(risk: RiskSection, breakout_positions_max: int) -> list[Row]:
    return [
        Row(
            field="Position cap",
            value=f"At most {risk.positions_max} positions open at once, counting orders already "
            "placed but not yet filled.",
            source="portfolio.py · enter",
        ),
        Row(
            field="Breakout cap",
            value=f"At most {breakout_positions_max} breakout positions open at once "
            "across both breakout strategies, including pending entries.",
            source="strategies/breakout.py · cap_keys",
        ),
        Row(
            field="Exposure",
            value="An entry is skipped if its estimated value would put gross exposure "
            "above account equity. Exposure includes pending entries.",
            source="portfolio.py · enter",
        ),
        Row(
            field="One owner per symbol",
            value="Only one strategy holds a symbol at a time; the others skip it while "
            "that position is open.",
            source="portfolio.py · _is_owned",
        ),
        Row(
            field="Daily loss limit",
            value=f"If equity falls {percent(risk.per_day_max)} below the session's opening "
            "value, every position is closed and no new trade is opened until the next session.",
            source="portfolio.py · _emergency_exit",
        ),
    ]


def _card(
    cls: type[Strategy], configuration: RuleSettings, opens: datetime, closes: datetime
) -> StrategyCard:
    described = _described(cls, configuration)
    rows = strategy_rows(described, configuration, opens, closes)
    if [row["field"] for row in rows] != list(RULE_FIELDS):
        raise ValueError(f"{cls.__name__} must describe every rule field in order")
    return StrategyCard(key=cls.key, name=cls.name(), kind=KINDS[cls.family], rows=rows)


def _described(cls: type[Strategy], configuration: RuleSettings) -> type[Strategy]:
    described = cast(type[Strategy], type(cls.__name__, (cls,), {}))
    described.bind(getattr(configuration, cls.key))
    if issubclass(described, Breakout):
        described.bind(configuration.breakout)
    return described


def _window(opens: datetime, closes: datetime) -> EntryWindow:
    return EntryWindow({"from": f"{opens:%H:%M}", "to": f"{closes:%H:%M}"})
