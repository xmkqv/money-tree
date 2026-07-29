# money-tree

An early-stage workspace for researching and defining a modular trading system.

## Documentation

- [Specification](spec.md)
- [Historical and bulk data](docs/data.md)
- [Live data APIs](docs/live.md)
- [Loaders](docs/loaders.md)
- [Transformers](docs/transformers.md)
- [Models](docs/models.md)
- [Deciders](docs/deciders.md)
- [Traders](docs/traders.md)

## Development

Requires Python 3.13 or newer and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --locked --all-packages
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv build --all-packages
```

## License

[MIT](LICENSE)
