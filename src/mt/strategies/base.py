from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import ClassVar, Protocol

from pandas import DataFrame

from mt.data.asset import Asset
from mt.rules.shared import settings
from mt.rules.values import TARGET_REASONS, OrderReason, StrategyKey
from mt.sizing import Direction, next_stop, round_quantity
from mt.state import EventLevel


@dataclass(frozen=True, slots=True)
class Session:
    now: datetime
    opens: datetime
    closes: datetime


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
    stage: int = 0

    def step(self, fraction: float, *, is_whole: bool = False) -> tuple[Decimal, OrderReason]:
        quantity = round_quantity(
            Decimal(str(self.original_quantity)) * Decimal(str(fraction)), is_whole=is_whole
        )
        reason = TARGET_REASONS[self.stage]
        self.stage += 1
        return quantity, reason


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

    def tighten_stop(self, stop: float, reason: OrderReason) -> None:
        raised = next_stop(self.direction, self.stop, stop)
        if raised != self.stop:
            self.stop, self.stop_reason = raised, reason


class Portfolio(Protocol):
    def assets(self) -> list[Asset]: ...

    def daily_frame(self, asset: Asset) -> DataFrame | None: ...

    def frames(
        self, assets: list[Asset], start: datetime, now: datetime, minutes: int
    ) -> dict[Asset, DataFrame]: ...

    def quote(self, asset: Asset) -> float | None: ...

    def holding_count(self, key: StrategyKey) -> int: ...

    def is_taken(self, strategy: Strategy, asset: Asset) -> bool: ...

    def enter(self, strategy: Strategy, candidate: Candidate, session: Session) -> bool: ...

    def exit(
        self, holding: Holding, reason: OrderReason, quantity: float | None = None
    ) -> None: ...

    def protect(self, holding: Holding, quantity: float | None = None) -> None: ...

    def record(self, strategy: Strategy, kind: str, level: EventLevel, message: str) -> None: ...


class Strategy(ABC):
    key: ClassVar[StrategyKey]
    code: ClassVar[str]
    family: ClassVar[str]
    variation: ClassVar[str]
    is_paused: ClassVar[bool]
    is_stop_resting: ClassVar[bool] = False
    holdings_max: ClassVar[int] = settings.risk.strategy_holdings_max

    def __init_subclass__(cls) -> None:
        if "key" not in cls.__dict__:
            return
        family, _, variation = cls.key.partition("_")
        cls.family = family
        if "variation" not in cls.__dict__:
            cls.variation = variation.upper() if variation.isalpha() else variation

    def __init__(self, portfolio: Portfolio) -> None:
        self.portfolio = portfolio

    @classmethod
    def name(cls) -> str:
        return f"{cls.family.capitalize()} {cls.variation}"

    @classmethod
    def symbols(cls) -> tuple[str, ...]:
        return ()

    @classmethod
    @abstractmethod
    def entry_window(cls, opens: datetime, closes: datetime) -> tuple[datetime, datetime]: ...

    @abstractmethod
    def run(self, session: Session) -> None: ...

    @abstractmethod
    def manage(self, holding: Holding, session: Session) -> None: ...

    def begin(self, session_on: date) -> None:
        return None

    def prepare(self, now: datetime) -> None:
        return None

    def ladder(self, holding: Holding, quantity: float) -> Ladder | None:
        return None

    def is_capped(self, now: datetime | None = None) -> bool:
        if self.portfolio.holding_count(self.key) < self.holdings_max:
            return False
        if now is not None:
            self.portfolio.record(
                self,
                f"entries.capped.{now.date()}",
                "info",
                f"{self.name()} entries paused: {self.holdings_max} holdings already open",
            )
        return True


def ranked[Item](
    items: Iterable[Item],
    *,
    symbol: Callable[[Item], str],
    score: Callable[[Item], float],
) -> list[Item]:
    return sorted(items, key=lambda item: (-score(item), symbol(item)))
