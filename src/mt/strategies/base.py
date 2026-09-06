from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date, datetime
from typing import ClassVar, Protocol

from pandas import DataFrame

from mt.config.settings import settings
from mt.position import Direction
from mt.snapshot import EventLevel

from .keys import StrategyKey


@dataclass(frozen=True, slots=True)
class Session:
    now: datetime
    opens: datetime
    closes: datetime


@dataclass(frozen=True, slots=True)
class Candidate:
    symbol: str
    price: float
    stop: float
    direction: Direction = 1


@dataclass(slots=True)
class Ladder:
    original_quantity: float
    targets: tuple[float, float, float]
    stage: int = 0


@dataclass(slots=True)
class Holding:
    strategy: "Strategy"
    symbol: str
    direction: Direction
    entry: float
    stop: float
    risk: float
    entered_at: datetime
    highest: float
    lowest: float
    ladder: Ladder | None = None


class Portfolio(Protocol):
    def eligible_symbols(self) -> list[str]: ...

    def daily_frame(self, symbol: str, now: datetime) -> DataFrame | None: ...

    def market_frame(self, now: datetime) -> DataFrame | None: ...

    def minute_frames(
        self, symbols: list[str], start: datetime, now: datetime, minutes: int
    ) -> dict[str, DataFrame]: ...

    def last_price(self, symbol: str) -> float: ...

    def position_count(self, keys: frozenset[StrategyKey]) -> int: ...

    def is_taken(self, strategy: "Strategy", symbol: str, day: date) -> bool: ...

    def enter(self, strategy: "Strategy", candidate: Candidate, session: Session) -> bool: ...

    def exit(self, holding: Holding, quantity: float | None = None) -> None: ...

    def protect(self, holding: Holding, quantity: float | None = None) -> None: ...

    def record(self, strategy: "Strategy", key: str, level: EventLevel, message: str) -> None: ...


class Strategy(ABC):
    key: ClassVar[StrategyKey]
    code: ClassVar[str]
    family: ClassVar[str]
    variation: ClassVar[str]
    is_paused: ClassVar[bool] = False
    is_stop_resting: ClassVar[bool] = False
    positions_max: ClassVar[int] = settings.risk.positions_max
    risk_fraction_max: ClassVar[float | None] = None

    def __init__(self, portfolio: Portfolio) -> None:
        self.portfolio = portfolio

    @classmethod
    def name(cls) -> str:
        return f"{cls.family.capitalize()} {cls.variation}"

    @classmethod
    def cap_keys(cls) -> frozenset[StrategyKey]:
        return frozenset({cls.key})

    @classmethod
    @abstractmethod
    def entry_window(cls, opens: datetime, closes: datetime) -> tuple[datetime, datetime]: ...

    @abstractmethod
    def run(self, session: Session) -> None: ...

    @abstractmethod
    def manage(self, holding: Holding, session: Session) -> None: ...

    def begin(self, day: date) -> None:
        return None

    def ladder(self, holding: Holding, original: float, remaining: float) -> Ladder | None:
        return None

    def is_capped(self) -> bool:
        return self.portfolio.position_count(self.cap_keys()) >= self.positions_max


def ranked[Item](
    items: Iterable[Item],
    *,
    symbol: Callable[[Item], str],
    turnover: Callable[[Item], float],
) -> list[Item]:
    return sorted(items, key=lambda item: (-turnover(item), symbol(item)))
