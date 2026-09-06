from datetime import date, datetime
from typing import TypedDict

from bot.config import settings
from bot.exchange import upcoming_session_bounds
from bot.strategies.base import RULE_FIELDS, Strategy
from bot.strategies.registry import STRATEGIES
from bot.types import RiskSection
from bot.universe import percent


class Row(TypedDict):
    field: str
    value: str
    source: str


class StrategyCard(TypedDict):
    id: str
    name: str
    kind: str
    rows: list[Row]


class StrategyRules(TypedDict):
    fields: list[str]
    strategies: list[StrategyCard]
    portfolio: list[Row]
    configured: bool


EntryWindow = TypedDict("EntryWindow", {"from": str, "to": str})


def entry_windows() -> dict[str, EntryWindow]:
    opens, closes = upcoming_session_bounds(date.today())
    return {cls.key: _window(*cls.entry_window(opens, closes)) for cls in STRATEGIES}


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
            "across both intraday strategies. The two strategies share one allowance, because "
            "every breakout is the same bet on the same half hour.",
            source="strategies/breakout.py · cap_keys",
        ),
        Row(
            field="Exposure",
            value="The total value held never exceeds account equity, so the account never "
            "trades on borrowed money.",
            source="portfolio.py · enter",
        ),
        Row(
            field="One owner per stock",
            value="Only one strategy holds a given stock at a time; the others skip it while "
            "that position is open.",
            source="portfolio.py · _is_claimed",
        ),
        Row(
            field="Daily loss limit",
            value=f"If equity falls {percent(risk.per_day_max)} below the previous close, every "
            "position is closed and no new trade is opened until the next session.",
            source="portfolio.py · _is_daily_loss_reached",
        ),
    ]


def _card(cls: type[Strategy], per_trade: float, opens: datetime, closes: datetime) -> StrategyCard:
    rules = cls.describe(per_trade, opens, closes)
    if [rule.field for rule in rules] != list(RULE_FIELDS):
        raise ValueError(f"{cls.__name__} must describe every rule field in order")
    return StrategyCard(
        id=cls.key,
        name=cls.name(),
        kind=cls.kind,
        rows=[Row(field=rule.field, value=rule.value, source=rule.source) for rule in rules],
    )


def _window(opens: datetime, closes: datetime) -> EntryWindow:
    return EntryWindow({"from": f"{opens:%H:%M}", "to": f"{closes:%H:%M}"})
