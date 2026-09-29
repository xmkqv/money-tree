import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar, Protocol

from pandas import DataFrame

from mt.data.asset import Asset
from mt.indicators import latest_atr
from mt.rules.sections import DailyVariationSection, StrategySection
from mt.rules.shared import settings
from mt.rules.values import TARGET_REASONS, OrderReason, StrategyKey
from mt.sizing import Direction, next_stop
from mt.state import EventLevel


type Take = tuple[OrderReason, float | None]


@dataclass(frozen=True, slots=True)
class Session:
    now: datetime
    opens_at: datetime
    closes_at: datetime


@dataclass(frozen=True, slots=True)
class Candidate:
    asset: Asset
    price: float
    stop: float
    direction: Direction = 1


@dataclass(slots=True)
class Ladder:
    original_quantity: float
    targets: tuple[float, ...]
    fractions: tuple[float, ...]
    stage: int = 0

    def try_take(self, price: float, direction: Direction) -> Take | None:
        if self.stage >= len(self.targets) or direction * (price - self.targets[self.stage]) < 0:
            return None
        reason = TARGET_REASONS[self.stage]
        if self.stage >= len(self.fractions):
            return reason, None
        shares = self.original_quantity * self.fractions[self.stage]
        self.stage += 1
        return reason, shares


@dataclass(slots=True)
class Holding:
    strategy: Strategy
    asset: Asset
    direction: Direction
    entry: float
    stop: float
    stop_distance: float
    entered_at: datetime
    highest: float
    lowest: float
    ladder: Ladder | None = None
    stop_reason: OrderReason = "stop"
    breakeven_at: datetime | None = None

    def mark(self, price: float) -> None:
        self.highest = max(self.highest, price)
        self.lowest = min(self.lowest, price)

    def tighten_stop(self, stop: float, reason: OrderReason) -> None:
        raised = next_stop(self.direction, self.stop, stop)
        if raised != self.stop:
            self.stop, self.stop_reason = raised, reason


class Portfolio(Protocol):
    def assets(self) -> list[Asset]: ...

    def get_daily_frame(self, asset: Asset) -> DataFrame | None: ...

    def frames(
        self, assets: list[Asset], start_at: datetime, now_at: datetime, minutes: int
    ) -> dict[Asset, DataFrame]: ...

    def quote(self, asset: Asset) -> float | None: ...

    def holding_count(self, key: StrategyKey) -> int: ...

    def is_taken(self, strategy: Strategy, asset: Asset) -> bool: ...

    def enter(self, strategy: Strategy, candidate: Candidate, session: Session) -> None: ...

    def exit(
        self, holding: Holding, reason: OrderReason, quantity: float | None = None
    ) -> None: ...

    def protect(self, holding: Holding, quantity: float | None = None) -> None: ...

    def record(self, strategy: Strategy, kind: str, level: EventLevel, message: str) -> None: ...


MINUTES_PATTERN = re.compile(r"\d+m")


class Strategy(ABC):
    key: ClassVar[StrategyKey]
    code: ClassVar[str]
    family: ClassVar[str]
    variation: ClassVar[str]
    rules: ClassVar[StrategySection]
    is_paused: ClassVar[bool]
    is_stop_resting: ClassVar[bool] = False
    holdings_max: ClassVar[int] = settings.risk.strategy_holdings_max

    def __init_subclass__(cls) -> None:
        if "key" not in cls.__dict__:
            return
        cls.family, _, cls.variation = cls.key.partition("_")
        cls.is_paused = cls.rules.is_paused
        if isinstance(cls.rules, DailyVariationSection):
            cls.holdings_max = cls.rules.holdings_max

    def __init__(self, portfolio: Portfolio) -> None:
        self.portfolio = portfolio

    @classmethod
    def name(cls) -> str:
        is_minutes = MINUTES_PATTERN.fullmatch(cls.variation)
        variation = cls.variation if is_minutes else cls.variation.upper()
        return f"{cls.family.capitalize()} {variation}"

    @classmethod
    @abstractmethod
    def entry_window(cls, opens_at: datetime, closes_at: datetime) -> tuple[datetime, datetime]: ...

    @abstractmethod
    def run(self, session: Session) -> None: ...

    @abstractmethod
    def manage(self, holding: Holding, session: Session) -> None: ...

    def begin(self, session: Session) -> None:
        return None

    def ladder(self, holding: Holding, quantity: float) -> Ladder | None:
        return None

    def is_capped(self, session: Session) -> bool:
        if self.portfolio.holding_count(self.key) < self.holdings_max:
            return False
        self.portfolio.record(
            self,
            f"entries.capped.{session.now.date()}",
            "info",
            f"{self.name()} entries paused: {self.holdings_max} holdings already open",
        )
        return True


def trail_distance(frame: DataFrame, multiple: float, period_bars: int) -> float | None:
    if len(frame) <= period_bars:
        return None
    return multiple * latest_atr(frame, period_bars)
