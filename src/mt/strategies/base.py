from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date, datetime
from typing import ClassVar, Protocol

from pandas import DataFrame

from mt.data.asset import Asset
from mt.rules.shared import settings
from mt.rules.values import STRATEGY_KEYS, SettingsSection, StrategyKey
from mt.sizing import Direction
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
    targets: tuple[float, float, float]
    stage: int = 0


@dataclass(slots=True)
class Holding:
    strategy: "Strategy"
    asset: Asset
    direction: Direction
    entry: float
    stop: float
    stop_distance: float
    entered_at: datetime
    highest: float
    lowest: float
    ladder: Ladder | None = None


class Portfolio(Protocol):
    def assets(self) -> list[Asset]: ...

    def daily_frame(self, asset: Asset) -> DataFrame | None: ...

    def benchmark_frame(self) -> DataFrame | None: ...

    def minute_frames(
        self, assets: list[Asset], start: datetime, now: datetime, minutes: int
    ) -> dict[Asset, DataFrame]: ...

    def last_price(self, asset: Asset) -> float: ...

    def is_earnings_blocked(self, asset: Asset, day: date) -> bool: ...

    def is_earnings_exit_due(self, asset: Asset, day: date) -> bool: ...

    def holding_count(self, keys: frozenset[StrategyKey]) -> int: ...

    def is_taken(self, strategy: "Strategy", asset: Asset, day: date) -> bool: ...

    def enter(self, strategy: "Strategy", candidate: Candidate, session: Session) -> bool: ...

    def exit(self, holding: Holding, quantity: float | None = None) -> None: ...

    def protect(self, holding: Holding, quantity: float | None = None) -> None: ...

    def record(self, strategy: "Strategy", kind: str, level: EventLevel, message: str) -> None: ...


class Strategy(ABC):
    key: ClassVar[StrategyKey]
    code: ClassVar[str]
    family: ClassVar[str]
    variation: ClassVar[str]
    is_paused: ClassVar[bool] = False
    is_stop_resting: ClassVar[bool] = False
    holdings_max: ClassVar[int] = settings.risk.strategy_holdings_max

    def __init_subclass__(cls) -> None:
        if "key" not in cls.__dict__:
            return
        family, _, variation = cls.key.partition("_")
        cls.family = family
        cls.variation = variation.upper() if variation.isalpha() else variation
        section: SettingsSection = getattr(settings, cls.key)
        missing = sorted(set(type(section).model_fields) - cls.bind(section))
        if missing:
            raise ValueError(f"{cls.__name__} must declare {cls.key} settings: {missing}")

    @classmethod
    def bind(cls, section: SettingsSection) -> set[str]:
        declared = {name for owner in cls.__mro__ for name in getattr(owner, "__annotations__", {})}
        bound = declared & set(type(section).model_fields)
        for name in bound:
            setattr(cls, name, getattr(section, name))
        return bound

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

    def ladder(self, holding: Holding, quantity: float) -> Ladder | None:
        return None

    def is_capped(self) -> bool:
        return self.portfolio.holding_count(self.cap_keys()) >= self.holdings_max


def family_keys(family: str) -> frozenset[StrategyKey]:
    return frozenset(key for key in STRATEGY_KEYS if key.startswith(f"{family}_"))


def ranked[Item](
    items: Iterable[Item],
    *,
    symbol: Callable[[Item], str],
    turnover: Callable[[Item], float],
) -> list[Item]:
    return sorted(items, key=lambda item: (-turnover(item), symbol(item)))
