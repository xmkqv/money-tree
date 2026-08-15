---
name: README
---

```sh
uv lock --check
uv run ruff check .
uv run ruff format --check .
uv run ty check
uv run python -m unittest discover -s tests -p 'test_*.py'
uv build
```

```sh
ntn ...
```

## railway

The Railway worker reads these variables at startup:

- `MONEY_TREE_STRATEGY` accepts `opening-range` or `momentum-long`.
- `MONEY_TREE_IS_LIVE` accepts `true` or `false`.
- an absent `MONEY_TREE_IS_LIVE` value selects paper trading.

Set the paper opening-range worker:

```sh
railway variable set MONEY_TREE_STRATEGY=opening-range MONEY_TREE_IS_LIVE=false --service money-tree
```

Set the paper momentum worker:

```sh
railway variable set MONEY_TREE_STRATEGY=momentum-long MONEY_TREE_IS_LIVE=false --service money-tree
```

Set the live opening-range worker:

```sh
railway variable set MONEY_TREE_STRATEGY=opening-range MONEY_TREE_IS_LIVE=true --service money-tree
```

CAUTION: Change these variables only when the selected broker account is flat.

A restart removes local ownership state. The worker stops when the broker contains unknown positions or orders.
