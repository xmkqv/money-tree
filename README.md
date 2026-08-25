# money-tree

Four US-equity trading strategies, written down first and then run: backtesting,
multi-strategy portfolio composition, and Alpaca execution.

The register below is the specification. `src/bot/strategies/` implements it, and
`STRATEGY_LABELS` in `src/bot/types.py` lists what actually runs.

[![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![python: 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](pyproject.toml)

> This is a personal project. It carries no performance record, no returns, and no
> track record of any kind. Nothing here is financial advice. Trading loses money.

## quickstart

```sh
uv sync
uv run pytest
```

Backtest a daily strategy and write a run directory. Daily strategies read from
Yahoo, so this needs no credentials.

```sh
uv run mt report --strategy sma --symbols SPY --start 2023-01-01 --end 2024-01-01
# runs/sma-20230101-20240101
```

The run directory holds `trades.csv`, `stats.csv`, `indicators.csv`, their parquet
equivalents, `tearsheet.html`, and `backtest.log`.

Intraday strategies (`orb`, `orb_momentum`) resolve minute bars through Alpaca and
fail without credentials. Copy `.env.example` to `.env` and fill in
`ALPACA_API_KEY` and `ALPACA_API_SECRET` first.

```sh
uv run mt backtest --strategy orb --symbols SPY --start 2023-01-01 --end 2024-01-01
```

Run live or paper against the broker. `ALPACA_IS_PAPER` decides which.

```sh
uv run mt trade --strategies orb,sma
```

The dashboard is a FastAPI app under `src/ui/`, deployed to Railway from
`.railway/railway.ts`. `spec.md` maps the layout, and `.railway/README.md` covers
the infrastructure commands.

## strategy register

### common terms

```text:types
ET = US Eastern Time
account = account value when the position opens
position value = money allocated to one position
breakeven = entry price
opening range size = opening range high - opening range low
opening range level(p) = opening range low + p * opening range size
SMA(n) = simple moving average over n candles
ATR(n) = average true range over n candles
RSI(n) = relative strength index over n candles
ADX = average directional index
MACD = moving average convergence divergence
none = the strategy does not use this rule
not set = no rule was provided
```

### enabled strategies

#### ORB (5-minute)

```text:surface
status
    state = enabled

market
    asset = US stocks
    market cap >= $500 million
    average daily volume >= 1 million shares
    market state = none
    direction = long or short

setup
    timeframe = 5-minute candles
    opening range = 09:30-09:35 ET
    marks = opening range high, midpoint, and low
    volume = cumulative volume >= 1.3 * 20-day average cumulative volume at the same time
    other filters = none

entry
    window = 09:35-10:30 ET
    long signal = first candle close above the opening range high
    short signal = first candle close below the opening range low
    order = next 5-minute candle open, directly after the signal candle
    earnings block = none
    open positions may remain after the entry window

risk
    position size = 10% of account
    risk per trade = 10% of position value
    risk-to-reward ratio = not set
    R = absolute(entry price - initial stop)
    long initial stop = opening range level(0.75)
    short initial stop = opening range level(0.25)
    at +1.5R set stop = breakeven
    at +1.5R enable trailing stop = 1.5 * ATR(14) on 5-minute candles
    active stop cannot move past breakeven into a loss

exit
    at +1.5R close = 50% of original position
    at +2.5R close = 25% of original position
    at +4R close = remaining 25% of original position
    signal exit = none
    earnings exit = none
    deadline = close any remaining position before 15:55 ET
    shared rules = none
```

#### ORB (10-minute)

```text:surface
status
    state = enabled

market
    asset = US stocks
    market cap >= $500 million
    average daily volume >= 1 million shares
    market state = none
    direction = long or short

setup
    timeframe = 10-minute candles
    opening range = 09:30-09:40 ET
    marks = opening range high, midpoint, and low
    volume = cumulative volume >= 1.5 * 20-day average cumulative volume at the same time
    long MACD = increasing
    short MACD = decreasing
    remove the MACD filter if it reduces trade count without raising average return

entry
    window = 09:40-10:30 ET
    long signal = first candle close above the opening range high
    short signal = first candle close below the opening range low
    order = next 10-minute candle open, directly after the signal candle
    earnings block = none
    open positions may remain after the entry window

risk
    position size = 10% of account
    risk per trade = not set
    risk-to-reward ratio = 1:2
    R = not set
    long initial stop = opening range level(0.75)
    short initial stop = opening range level(0.25)
    at PT(0.5) set stop = breakeven
    at PT(0.5) enable trailing stop = 1.5 * ATR(14) on 10-minute candles
    active stop cannot move past breakeven into a loss

exit
    long PT(n) = opening range high + n * opening range size
    short PT(n) = opening range low - n * opening range size
    at PT(0.5) close = 50% of original position
    at PT(1.0) close = 25% of original position
    at PT(2.0) close = remaining 25% of original position
    signal exit = none
    earnings exit = none
    deadline = close any remaining position before 15:55 ET
    shared rules = none
```

#### Momentum (SMA)

```text:surface
status
    state = enabled

market
    asset = US stocks
    market cap >= $500 million
    average daily volume >= 1 million shares
    market state = SPX > SMA(20)
    direction = long

setup
    timeframe = daily candles
    opening range = none
    marks = none
    price = price > SMA(50) > SMA(200)
    momentum = 50 <= RSI <= 70 and ADX >= 25

entry
    window = market open on day 3
    day 1 = close < SMA(20)
    day 2 = close > SMA(20)
    long signal = day 1 and day 2 rules pass
    order = day 3 market open
    earnings block = no new entry within 5 days before earnings

risk
    position size = 10% of account
    risk per trade = not set
    risk-to-reward ratio = not set
    R = not set
    initial stop = highest close since entry - 1.5 * ATR(14)
    stop update = recalculate daily from the highest close since entry
    stop can only move up
    stop exit = daily close below stop, then exit at next market open

exit
    profit targets = none
    signal exit = daily close < SMA(20) and RSI(14) < 50
    earnings exit = close any open position on the day before earnings
    deadline = none
    shared rules = Stop Loss and Emergency Exit
```

#### TFB-50

```text:surface
status
    state = enabled

market
    asset = US stocks
    market cap >= $500 million
    average daily volume >= 1 million shares
    market state = SPX > SMA(20)
    direction = long

setup
    timeframe = daily candles
    opening range = none
    marks = none
    price = price > SMA(50) and SMA(50) > SMA(50) from 3 candles ago
    momentum = ADX >= 20

entry
    window = next market open
    long signal = daily close > previous candle high
    short signal = none
    order = market open after the signal candle
    earnings block = none

risk
    position size = 10% of account
    risk per trade = not set
    risk-to-reward ratio = none
    R = not set
    initial stop = entry price - 2 * ATR(14)
    stop update = highest close since entry - 2 * ATR(14), recalculated daily
    stop can only move up
    stop exit = daily close below stop, then exit at next market open

exit
    profit targets = none
    signal exit = daily close < SMA(20) and RSI(14) < 50
    earnings exit = close any open position on the day before earnings
    deadline = none
    shared rules = Stop Loss and Emergency Exit
```


## license

MIT. See [LICENSE](LICENSE).
