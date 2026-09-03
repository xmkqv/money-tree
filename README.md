# money-tree

Four US-equity trading strategies, written down first and then run: backtesting,
multi-strategy portfolio composition, and Alpaca execution.

The register below is the specification. `src/bot/strategies/` implements it,
`STRATEGY_LABELS` in `src/bot/types.py` lists what actually runs, and
`PAUSED_STRATEGIES` there names the strategies that take no new entries.

[![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![python: 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](pyproject.toml)

> This is a personal project. It carries no performance record, no returns, and no
> track record of any kind. Nothing here is financial advice. Trading loses money.

## quickstart

Every command runs in a mode. Make development the shell default; production is
selected per invocation.

```sh
export MISE_ENV=development
mise run setup
```

`mise.development.toml` declares every variable the bot and the dashboard read.
The ones declared empty are secrets: write them into `.env.development`, which
mise loads last and never tracks.

`mise.production.toml` is the corresponding production contract. Set its public
deployment URLs there, and put credentials, allowed emails, signing secrets, and
`RAILWAY_TOKEN` in `.env.production`; mise loads that ignored file last as well.
Neither mode inherits values from the other.

```sh
mise run check
```

Backtest a daily strategy and write a run directory.

```sh
mise exec -- uv run mt report --strategy sma --symbols SPY --start 2023-01-01 --end 2024-01-01
# runs/sma-20230101-20240101
```

The run directory holds `trades.csv`, `stats.csv`, `indicators.csv`, their parquet
equivalents, `tearsheet.html`, and `backtest.log`.

Intraday strategies (`orb`, `orb_momentum`) resolve minute bars through Alpaca.

```sh
mise exec -- uv run mt backtest --strategy orb --symbols SPY --start 2023-01-01 --end 2024-01-01
```

Run against the broker. The mode decides paper or live: development sets
`ALPACA_IS_PAPER=true`, production sets it false.

```sh
mise exec -- uv run mt trade --strategies orb
mise --env production exec -- uv run mt trade --strategies orb
```

The dashboard is a FastAPI app under `src/ui/`, deployed to Railway from
`.railway/railway.ts`. `spec.md` maps the layout, and `.railway/README.md` covers
the infrastructure commands. The deploy task publishes the production mise
environment into each Railway service, so Railway is a target rather than a
second configuration owner.

```sh
mise run serve
mise run stop
mise --env production run deploy HEAD
```

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
whole shares only = every leg of the position rounds down to a whole number, because a
    broker lends shares and not fractions of one; a slice worth less than one share is skipped
none = the strategy does not use this rule
not set = no rule was provided
enabled = the strategy opens new positions and manages them
paused = the strategy opens no new positions; open ones run to their exit rules
rescan = the day's candidates are re-offered on every iteration to the close;
    a daily setup is cut from completed candles, so the list itself cannot
    change intraday, only the room to take it
```

### strategies

#### ORB (5-minute)

```text:surface
status
    state = enabled

market
    asset = US stocks
    market cap >= $500 million
    share price >= $5
    average daily turnover >= $20 million
    market state = none
    direction = long or short

setup
    timeframe = 5-minute candles
    opening range = 09:30-09:35 ET
    marks = opening range high, midpoint, and low
    volume = cumulative volume >= 1.3 * 20-day average cumulative volume at the same time
    opening range size >= 0.4% of price
    initial stop distance = 1% to 5% of price
    volume is read as of the signal candle's close
    other filters = none

sorting
    rank = last completed daily session close * volume, highest first
    applies when more breakouts fire than there is room to hold

entry
    window = 09:35-10:30 ET
    long signal = first candle close above the opening range high
    short signal = first candle close below the opening range low
    signal candle = the first such candle since the range, within the last 2 completed candles
    order = next 5-minute candle open, directly after the signal candle
    entry block = live quote already through the initial stop
    earnings block = none
    open positions may remain after the entry window

risk
    position size = 10% of account
    short position size = whole shares only
    risk per trade = 0.15% of account equity
    concurrent breakout positions = 3, shared across both intraday engines
    risk-to-reward ratio = not set
    R = absolute(entry price - initial stop)
    long initial stop = opening range level(0.75)
    short initial stop = opening range level(0.25)
    at +1.5R set stop = breakeven
    at +1.5R enable trailing stop = 1.5 * ATR(14) on 5-minute candles
    ATR(14) window = 5-minute candles across sessions, prior-session bars used as needed
    overnight gaps contribute to true range
    ATR(14) needs 15 completed 5-minute candles, normally already available at entry
    active stop cannot move past breakeven into a loss
    stop at or beyond the last price = close the position at market

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
    state = paused

market
    asset = US stocks
    market cap >= $500 million
    share price >= $5
    average daily turnover >= $20 million
    market state = none
    direction = long or short

setup
    timeframe = 10-minute candles
    opening range = 09:30-09:40 ET
    marks = opening range high, midpoint, and low
    volume = cumulative volume >= 1.5 * 20-day average cumulative volume at the same time
    opening range size >= 0.4% of price
    initial stop distance = 1% to 5% of price
    volume is read as of the signal candle's close
    other filters = none

sorting
    rank = last completed daily session close * volume, highest first
    applies when more breakouts fire than there is room to hold

entry
    window = 09:40-10:30 ET
    long signal = first candle close above the opening range high
    short signal = first candle close below the opening range low
    signal candle = the first such candle since the range, within the last 2 completed candles
    order = next 10-minute candle open, directly after the signal candle
    entry block = live quote already through the initial stop
    long max entry price = opening range high + 0.25 * opening range size
    short min entry price = opening range low - 0.25 * opening range size
    earnings block = none
    open positions may remain after the entry window

risk
    position size = 10% of account
    short position size = whole shares only
    risk per trade = not set
    concurrent breakout positions = 3, shared across both intraday engines
    risk-to-reward ratio = 1:2
    R = absolute(entry price - initial stop)
    long initial stop = opening range level(0.75)
    short initial stop = opening range level(0.25)
    at +2R set stop = breakeven
    at +2R enable trailing stop = 1.5 * ATR(14) on 10-minute candles
    ATR(14) window = 10-minute candles across sessions, prior-session bars used as needed
    overnight gaps contribute to true range
    ATR(14) needs 15 completed 10-minute candles, normally already available at entry
    active stop cannot move past breakeven into a loss
    stop at or beyond the last price = close the position at market

exit
    at +2R close = 50% of original position
    at +3R close = 25% of original position
    at +5R close = remaining 25% of original position
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
    share price >= $5
    average daily turnover >= $20 million
    market state = SPX > SMA(20)
    direction = long

setup
    timeframe = daily candles
    opening range = none
    marks = none
    price = price > SMA(50) > SMA(200)
    momentum = RSI >= 50 and ADX >= 25

sorting
    rank = last completed session close * volume, highest first
    applies when more symbols qualify than there is room to hold

entry
    window = day 3 market open to market close, rescan
    day 1 = close < SMA(20)
    day 2 = close > SMA(20) and close > day 1 close
    long signal = day 1 and day 2 rules pass
    order = day 3 market open, or the first later iteration at which a position
        slot and the money for it are free
    one entry per symbol per session
    earnings block = no new entry within 5 days before earnings,
        ignored when no earnings date is known

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
    signal exit = daily close < SMA(20) or RSI(14) < 50
    earnings exit = close any open position on the day before earnings,
        ignored when the earnings calendar cannot be read
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
    share price >= $5
    average daily turnover >= $20 million over the last 20 sessions
    market state = SPX > SMA(20)
    direction = long

setup
    timeframe = daily candles
    opening range = none
    marks = none
    price = price > SMA(50) and SMA(50) > SMA(50) from 3 sessions ago
    momentum = ADX >= 20

sorting
    rank = last completed session close * volume, highest first
    applies when more symbols qualify than there is room to hold

entry
    window = market open to market close, rescan
    long signal = daily close > previous candle high
    short signal = none
    order = market open after the signal candle, or the first later iteration
        at which a position slot and the money for it are free
    earnings block = none
    max positions = 5
    one entry per symbol per session

risk
    position size = 10% of account
    risk per trade = 0.5% of account
    risk-to-reward ratio = none
    R = not set
    initial stop = entry price - 2 * ATR(14)
    stop update = highest close since entry - 2 * ATR(14), recalculated daily
    stop can only move up
    stop exit = daily close below stop, then exit at next market open

exit
    profit targets = none
    signal exit = daily close < SMA(20) or RSI(14) < 50
    earnings exit = none
    deadline = none
    shared rules = Stop Loss and Emergency Exit
```


## license

MIT. See [LICENSE](LICENSE).
