# money-tree

US-equity trading strategies
- backtesting
- multi-strategy portfolio composition
- Alpaca execution

[![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![python: 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](pyproject.toml)

## quickstart

```sh
export MISE_ENV=development
mise run setup
mise run test
mise exec -- uv run mt report --strategy daily_sma --symbols SPY --start 2023-01-01 --end 2024-01-01
# runs/daily_sma-20230101-20240101
mise exec -- uv run mt trade --strategies breakout_5m
mise --env production exec -- uv run mt trade --strategies breakout_5m
mise run serve
mise run stop
mise --env production run deploy
```

## license

MIT. See [LICENSE](LICENSE).
