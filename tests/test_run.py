from money_tree.data import MarketState, Stage
from money_tree.decide import TargetPositions
from money_tree.execute import Positions
from money_tree.pipeline import run
from money_tree.predict import Forecast


def test_run_executes_the_complete_pipeline() -> None:
    completed: list[Stage] = []

    positions = run(
        source=lambda: MarketState({"AAPL": 200.0}),
        model=lambda state: Forecast({"AAPL": state.values["AAPL"] / 2000}),
        policy=lambda forecast: TargetPositions({"AAPL": forecast.outcomes["AAPL"] * 10}),
        broker=lambda targets: Positions(targets.quantities),
        observer=lambda stage, _: completed.append(stage),
    )

    assert positions == Positions({"AAPL": 1.0})
    assert completed == ["data", "predict", "decide", "execute"]
