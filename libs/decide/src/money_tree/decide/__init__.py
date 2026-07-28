"""Position decision contracts."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from money_tree.data import Observer
from money_tree.predict import Forecast

__all__ = ["Policy", "TargetPositions", "decide"]


@dataclass(frozen=True, slots=True)
class TargetPositions:
    quantities: Mapping[str, float]


type Policy = Callable[[Forecast], TargetPositions]


def decide(policy: Policy, forecast: Forecast, observer: Observer) -> TargetPositions:
    targets = policy(forecast)
    observer("decide", targets)
    return targets
