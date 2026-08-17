# Money Tree

```sh
# analyze
uv run python src/analysis/break-even-accuracy.py data/sessions.csv

# backtest report
uv run mt report --strategy <name> --symbols A,B,C --start 2022-01-01 --end 2025-12-31 [--label "Display Name"]
```

`mt report` writes a self-contained run directory (`report.md`, `report.json`, chart PNGs).
