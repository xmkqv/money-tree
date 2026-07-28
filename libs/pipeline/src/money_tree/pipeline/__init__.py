"""Orchestration for the complete money-tree pipeline."""

from money_tree.data import MarketState, Observer, Source, load
from money_tree.decide import Policy, TargetPositions, decide
from money_tree.execute import Broker, Positions, execute
from money_tree.predict import Forecast, Model, predict

__all__ = [
    "Broker",
    "Forecast",
    "MarketState",
    "Model",
    "Observer",
    "Policy",
    "Positions",
    "Source",
    "TargetPositions",
    "run",
]


def run(
    source: Source,
    model: Model,
    policy: Policy,
    broker: Broker,
    observer: Observer,
) -> Positions:
    """Run each pipeline stage once and return the resulting positions."""
    state = load(source, observer)
    forecast = predict(model, state, observer)
    targets = decide(policy, forecast, observer)
    return execute(broker, targets, observer)
