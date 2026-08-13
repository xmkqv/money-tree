# money tree

money tree is an alpha opening-range breakout trader for alpaca and lumibot.
it trades spy by default and limits planned loss to $0.80 per trade.
it disables entries and sends a flatten request when the daily loss reaches $1.00.

## setup

1. install python 3.13 and uv.
2. run `uv sync --locked`.
3. copy `.env.example` to `.env` and add alpaca credentials.
4. export the required variables before you run the command.

paper credentials use `ALPACA_API_KEY` and `ALPACA_API_SECRET`.
live credentials use `ALPACA_LIVE_API_KEY` and `ALPACA_LIVE_API_SECRET`.

## use

run a backtest:

```sh
uv run money-tree backtest --start 2026-06-01 --end 2026-08-01
```

run live trading:

```sh
uv run money-tree live --confirm-live
```

run paper trading:

```sh
uv run money-tree paper
```

live trading writes recovery state to `.money-tree/orb-state.json` by default.
paper trading writes recovery state to `.money-tree/orb-paper-state.json` by default.
startup stops if spy has a position or order that the saved state does not own.

## validate

```sh
uv lock --check
uv run ruff check .
uv run ruff format --check .
uv run ty check
uv build
```

see [spec.md](spec.md) for the strategy and risk rules.

this software can place live orders and lose money.
