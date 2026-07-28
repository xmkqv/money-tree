"""Market data contracts."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Literal

__all__ = ["MarketState", "Observer", "Source", "Stage", "load"]

type Stage = Literal["data", "predict", "decide", "execute"]
type Observer = Callable[[Stage, object], None]


@dataclass(frozen=True, slots=True)
class MarketState:
    values: Mapping[str, float]


type Source = Callable[[], MarketState]


def load(source: Source, observer: Observer) -> MarketState:
    state = source()
    observer("data", state)
    return state
