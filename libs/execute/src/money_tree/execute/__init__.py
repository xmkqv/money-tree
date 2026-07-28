"""Market execution contracts."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from money_tree.data import Observer
from money_tree.decide import TargetPositions

__all__ = ["Broker", "Positions", "execute"]


@dataclass(frozen=True, slots=True)
class Positions:
    quantities: Mapping[str, float]


type Broker = Callable[[TargetPositions], Positions]


def execute(broker: Broker, targets: TargetPositions, observer: Observer) -> Positions:
    positions = broker(targets)
    observer("execute", positions)
    return positions
