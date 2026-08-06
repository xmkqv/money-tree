# money-tree

An early-stage workspace for researching and defining a modular trading system.

## Layers

Every layer exposes one interface of the shape `(config, input) → output`, and the
config selects the instance. Composition and execution belong to the caller.

| Layer | Owns | Interface |
| --- | --- | --- |
| `data` | access | `data(data_config, source): grain` |
| `models` | transform and predict | `model(model_config, grain): prediction` |
| `deciders` | decision formation | `decider(decider_config, prediction): decision` |
| `traders` | decision execution | `trader(trader_config, decision): outcome` |

The data pipe is locked to `grain(dlt(source))`. Live and past sources are tentative.

## Documentation

- [Specification](spec.md)
- [Data](docs/data.md)
- [Feeds](docs/feeds.md)
- [Models](docs/models.md)
- [Deciders](docs/deciders.md)
- [Traders](docs/traders.md)

## Development

Requires Python 3.13 or newer and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --locked
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv build
```

## License

[MIT](LICENSE)
