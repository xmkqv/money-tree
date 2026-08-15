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
STRATEGIES_TABLE_LINK=https://app.notion.com/p/3bc2876aac868047b66dcee40b46b9b2?v=3bc2876aac868032a476000c765c1ee5&source=copy_link

ntn ...
```

## railway

The Railway worker reads these variables at startup:

- `MONEY_TREE_STRATEGY` accepts `opening-range`, `momentum-long`, or `tfb-50`.
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

Set the paper TFB-50 worker:

```sh
railway variable set MONEY_TREE_STRATEGY=tfb-50 MONEY_TREE_IS_LIVE=false --service money-tree
```

Set the live opening-range worker:

```sh
railway variable set MONEY_TREE_STRATEGY=opening-range MONEY_TREE_IS_LIVE=true --service money-tree
```

Set the live TFB-50 worker:

```sh
railway variable set MONEY_TREE_STRATEGY=tfb-50 MONEY_TREE_IS_LIVE=true --service money-tree
```

CAUTION: If the selected broker account is not flat, do not change these variables.

A restart removes local ownership state.

If the broker contains unknown positions or orders, the worker stops.
