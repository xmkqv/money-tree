# money-tree

Four US-equity trading strategies, written down first and then run: backtesting,
multi-strategy portfolio composition, and Alpaca execution.

[![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![python: 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](pyproject.toml)

> This is a personal project. It carries no performance record, no returns, and no
> track record of any kind. Nothing here is financial advice. Trading loses money.

[spec](spec.md)

## quickstart

Every command runs in an environment. Make development the shell default.
Select production per invocation.

```sh
export MISE_ENV=development
mise run setup
mise run test
```

Replay a strategy over a date range into a run directory.

```sh
mise exec -- uv run mt report --strategy daily_sma --symbols SPY --start 2023-01-01 --end 2024-01-01
# runs/daily_sma-20230101-20240101
```

Trade. The environment picks the settings; `BROKER__MODE` picks paper or live.

```sh
mise exec -- uv run mt trade --strategies breakout_5m
mise --env production exec -- uv run mt trade --strategies breakout_5m
```

Serve the dashboard and stop it. `mise run deploy` ships both services at one revision.

```sh
mise run serve
mise run stop
```

## license

MIT. See [LICENSE](LICENSE).

Daily replay uses engine daily bars; it does not establish minute-level fill fidelity.
