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

Backtest a strategy over a date range into a run directory.

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

## vocabulary

Realtime describes current observations. A series contains observations ordered by
time; historical describes earlier observations. Lookback settings set the amount
of earlier data requested. Bars clients retrieve price and volume series; trading
clients retrieve account data, including account series.

Assets use Alpaca's `Asset` model and retain instrument capabilities. Positions
name both broker exposure and strategy management state, qualified by source where
needed. `mt report` runs a backtest and writes its report.

Bar feed and timeout settings use `BARS__*`. Data windows use `LOOKBACK_DAYS` or
`LOOKBACK_SESSIONS`, including prefixed windows such as `CONFIRM_LOOKBACK_DAYS`.
Remove old `PAST__*` and `*_PAST_DAYS`/`*_PAST_SESSIONS` environment overrides
before starting either service; stale nested keys fail settings validation.
Backtests construct asset metadata from `BACKTEST__ASSET_DEFAULTS`; the configured
capabilities are simulation assumptions, not historical broker eligibility.

## license

MIT. See [LICENSE](LICENSE).

Daily backtest uses engine daily bars; it does not establish minute-level fill fidelity.
