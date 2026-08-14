# money tree

domain names and their meanings are in [names.yaml](names.yaml).
both strategies support backtest, paper, and live trading.

## strategies

- `opening-range`
- `momentum-long`

both strategies use spy as the default instrument.

## setup

1. install python 3.13 and uv.
2. run `uv sync --locked`.
3. copy `.env.example` to `.env`.
4. add the required alpaca credentials.

paper credentials use `ALPACA_API_KEY` and `ALPACA_API_SECRET`.
live credentials use `ALPACA_LIVE_API_KEY` and `ALPACA_LIVE_API_SECRET`.

## backtest

```sh
money-tree strategy backtest opening-range --instrument SPY
money-tree strategy backtest momentum-long --instrument SPY
```

use `--start`, `--end`, and `--out` to change the session range and report directory.

## paper trading

```sh
money-tree strategy trade opening-range --mode paper --instrument SPY
money-tree strategy trade momentum-long --mode paper --instrument SPY
```

## live trading

```sh
money-tree strategy trade opening-range --mode live --confirm live
money-tree strategy trade momentum-long --mode live --confirm live
```

live trading requires the literal `--confirm live` argument.

## recovery

the default state files are:

- `.money-tree/opening-range-paper-state.json`
- `.money-tree/opening-range-live-state.json`
- `.money-tree/momentum-long-paper-state.json`
- `.money-tree/momentum-long-live-state.json`

startup stops when a broker position is not an owned position or a broker order is not an owned order.
each order and fill transition saves state with an atomic file replacement.
legacy `orb` state files are not loaded automatically.

## validate

```sh
uv lock --check
uv run ruff check .
uv run ruff format --check .
uv run ty check
uv run python -m unittest discover -s tests -p 'test_*.py'
uv build
```

see [spec.md](spec.md) for behavior and [names.yaml](names.yaml) for root names.
the [research specification](research/spec.md) describes a separate aapl experiment.

this software can submit live orders and lose money.
