"""Forecast contracts."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from money_tree.data import MarketState, Observer

__all__ = ["Forecast", "Model", "predict"]


@dataclass(frozen=True, slots=True)
class Forecast:
    outcomes: Mapping[str, float]


type Model = Callable[[MarketState], Forecast]


def predict(model: Model, state: MarketState, observer: Observer) -> Forecast:
    forecast = model(state)
    observer("predict", forecast)
    return forecast
