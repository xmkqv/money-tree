# Money Tree

Money Tree uses the strategy pattern from the [Lumibot README](https://github.com/Lumiwealth/lumibot#quick-start).

## Backtest

Run the README strategy against Yahoo data.

```sh
uv sync
uv run mt backtest --strategy readme --start 2023-01-01 --end 2024-01-01
```

## Trade

Set the Alpaca variables in `.env`.

```sh
STRATEGY=readme
BACKTEST_START=2023-01-01
BACKTEST_END=2024-01-01
ALPACA_API_KEY=your-alpaca-key
ALPACA_API_SECRET=your-alpaca-secret
ALPACA_IS_PAPER=true
RISK_PER_DAY_MAX=0.02
RISK_PER_TRADE_MAX=0.005
```

Run the same strategy with Alpaca.

```sh
uv run mt trade --strategy readme
```

Each strategy module in `src/bot/strategies` exports a class named `Strategy`.
The runner passes both risk limits to the strategy as Lumibot parameters.

## Railway

The private worker uses `railway.toml`.
The public web service uses `railway.web.toml`.

The worker starts `mt trade` with the `STRATEGY` variable.
The web service starts Uvicorn on `0.0.0.0:$PORT`.

Create a confidential OAuth application in the Railway workspace.
Set its callback to `https://<generated-domain>/auth/callback`.
Set the web variables from `.env.example` on `money-tree-web`.

The web service accepts only the two subjects in `ALLOWED_RAILWAY_SUBS`.
Do not set Alpaca credentials on the web service.

## Analysis

The break-even script reads these CSV columns:

- `usd_absolute_price_move`
- `usd_transaction_cost`

```sh
uv run python src/analysis/break-even-accuracy.py data/sessions.csv
```
