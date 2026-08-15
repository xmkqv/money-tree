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