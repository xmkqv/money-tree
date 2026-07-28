from money_tree.data import MarketState, Stage, load
from money_tree.decide import TargetPositions, decide
from money_tree.execute import Positions, execute
from money_tree.predict import Forecast, predict


def test_pipeline_reports_each_completed_stage() -> None:
    stages: list[Stage] = []

    def observe(stage: Stage, _: object) -> None:
        stages.append(stage)

    state = load(lambda: MarketState({"AAPL": 200.0}), observe)
    forecast = predict(lambda _: Forecast({"AAPL": 0.1}), state, observe)
    targets = decide(lambda _: TargetPositions({"AAPL": 1.0}), forecast, observe)
    positions = execute(lambda target: Positions(target.quantities), targets, observe)

    assert (positions, stages) == (
        Positions({"AAPL": 1.0}),
        ["data", "predict", "decide", "execute"],
    )
