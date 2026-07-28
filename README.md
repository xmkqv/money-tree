# money-tree

Small, typed contracts and orchestration for a four-stage trading pipeline.

```text
Source -> load -> MarketState
Model + MarketState -> predict -> Forecast
Policy + Forecast -> decide -> TargetPositions
Broker + TargetPositions -> execute -> Positions
```

Each stage accepts a typed callable and reports its result to an `Observer`.
Logging, metrics, and safety controls stay separate from market and strategy
code.

> [!NOTE]
> Money-tree is an early-stage workspace. It defines the pipeline contracts but
> does not yet ship market-data or broker adapters.

## Public contract

| Name | Meaning |
| --- | --- |
| `Stage` | One of `data`, `predict`, `decide`, or `execute` |
| `Observer` | Callable that receives a completed stage and its result |
| `Source` | Callable that returns `MarketState` |
| `MarketState` | Immutable mapping of symbols to observed values |
| `Model` | Callable that transforms `MarketState` into `Forecast` |
| `Forecast` | Immutable mapping of symbols to predicted outcomes |
| `Policy` | Callable that transforms `Forecast` into `TargetPositions` |
| `TargetPositions` | Immutable mapping of symbols to desired quantities |
| `Broker` | Callable that transforms `TargetPositions` into `Positions` |
| `Positions` | Immutable mapping of symbols to obtained quantities |

Every stage calls the observer after its adapter returns.

## Packages

| Distribution | Import | Depends on |
| --- | --- | --- |
| `money-tree-data` | `money_tree.data` | Standard library |
| `money-tree-predict` | `money_tree.predict` | `money-tree-data` |
| `money-tree-decide` | `money_tree.decide` | Data and predict |
| `money-tree-execute` | `money_tree.execute` | Data and decide |
| `money-tree` | `money_tree.pipeline` | All four stages |

The packages use an implicit `money_tree` namespace, so applications can install
only the stages they need.

Value objects are frozen, slotted dataclasses. Workspace packages declare every
internal dependency and ship `py.typed` markers.

## Requirements

- Python 3.13 or newer
- [uv](https://docs.astral.sh/uv/)

## Quick start

```bash
git clone https://github.com/xmkqv/money-tree.git
cd money-tree
uv sync --locked --all-packages
```

```python
from money_tree.data import MarketState, Stage
from money_tree.decide import TargetPositions
from money_tree.execute import Positions
from money_tree.pipeline import run
from money_tree.predict import Forecast

completed: list[Stage] = []


def observe(stage: Stage, _: object) -> None:
    completed.append(stage)


positions = run(
    source=lambda: MarketState({"AAPL": 200.0}),
    model=lambda _: Forecast({"AAPL": 0.10}),
    policy=lambda _: TargetPositions({"AAPL": 1.0}),
    broker=lambda target: Positions(target.quantities),
    observer=observe,
)

print(positions)
print(completed)
```

## Development

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv build --all-packages
```

The workspace keeps tests, linting, formatting, typing, and package metadata in
the root [`pyproject.toml`](pyproject.toml).

## Reuse

Released under the [MIT License](LICENSE).
