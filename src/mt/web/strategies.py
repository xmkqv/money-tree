from datetime import date, datetime
from typing import TypedDict

from mt.config.sections import RiskSection
from mt.config.settings import settings
from mt.exchange import upcoming_session_bounds
from mt.strategies.base import Strategy
from mt.strategies.order_tag import ORDER_TAG_PREFIX, UNATTRIBUTED
from mt.strategies.registry import STRATEGIES

from .rules import KINDS, RULE_FIELDS, Row, percent, strategy_rows


class StrategyCard(TypedDict):
    id: str
    name: str
    kind: str
    rows: list[Row]


class StrategyLabel(TypedDict):
    id: str
    short: str
    label: str


class StrategyRules(TypedDict):
    fields: list[str]
    strategies: list[StrategyCard]
    portfolio: list[Row]
    configured: bool


EntryWindow = TypedDict("EntryWindow", {"from": str, "to": str})


def entry_windows() -> dict[str, EntryWindow]:
    opens, closes = upcoming_session_bounds(date.today())
    return {cls.key: _window(*cls.entry_window(opens, closes)) for cls in STRATEGIES}


def strategy_labels() -> list[StrategyLabel]:
    labels = [
        StrategyLabel(id=cls.key, short=cls.name(), label=f"{cls.name()} · {KINDS[cls.family]}")
        for cls in STRATEGIES
    ]
    labels.append(
        StrategyLabel(id=UNATTRIBUTED, short="Untagged", label=f"No {ORDER_TAG_PREFIX}- order tag")
    )
    return labels


def strategy_rules(risk: RiskSection, *, configured: bool) -> StrategyRules:
    opens, closes = upcoming_session_bounds(date.today())
    return StrategyRules(
        fields=list(RULE_FIELDS),
        strategies=[_card(cls, risk.per_trade_max, opens, closes) for cls in STRATEGIES],
        portfolio=portfolio_rules(risk),
        configured=configured,
    )


def portfolio_rules(risk: RiskSection) -> list[Row]:
    return [
        Row(
            field="Position cap",
            value=f"At most {risk.positions_max} positions open at once, counting orders already "
            "placed but not yet filled.",
            source="portfolio.py · enter",
        ),
        Row(
            field="Breakout cap",
            value=f"At most {settings.breakout.positions_max} breakout positions open at once "
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


def _card(cls: type[Strategy], per_trade: float, opens: datetime, closes: datetime) -> StrategyCard:
    rows = strategy_rows(cls, per_trade, opens, closes)
    if [row["field"] for row in rows] != list(RULE_FIELDS):
        raise ValueError(f"{cls.__name__} must describe every rule field in order")
    return StrategyCard(id=cls.key, name=cls.name(), kind=KINDS[cls.family], rows=rows)


def _window(opens: datetime, closes: datetime) -> EntryWindow:
    return EntryWindow({"from": f"{opens:%H:%M}", "to": f"{closes:%H:%M}"})
