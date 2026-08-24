# Money Tree

## Commands

```sh
# analyze
uv run python src/analysis/break-even-accuracy.py data/sessions.csv

# backtest report
uv run mt report --strategy <name> --symbols A,B,C --start 2022-01-01 --end 2025-12-31
```

## Strategy register

### Common terms

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

### Enabled strategies

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

### Disabled strategies

#### ORB (15-minute)

```text:surface
status
    state = disabled

market
    asset = not set
    market cap = not set
    average daily volume = not set
    market state = not set
    direction = not set

setup
    timeframe = 15-minute candles
    opening range = not set
    marks = not set
    volume = not set
    other filters = not set

entry
    window = not set
    long signal = not set
    short signal = not set
    order = not set
    earnings block = not set

risk
    position size = not set
    risk per trade = not set
    risk-to-reward ratio = not set
    R = not set
    initial stop = not set
    stop update = not set
    stop exit = not set

exit
    profit targets = not set
    signal exit = not set
    earnings exit = not set
    deadline = not set
    shared rules = not set
```

#### ORB (20-minute)

```text:surface
status
    state = disabled

market
    asset = not set
    market cap = not set
    average daily volume = not set
    market state = not set
    direction = not set

setup
    timeframe = 20-minute candles
    opening range = not set
    marks = not set
    volume = not set
    other filters = not set

entry
    window = not set
    long signal = not set
    short signal = not set
    order = not set
    earnings block = not set

risk
    position size = not set
    risk per trade = not set
    risk-to-reward ratio = not set
    R = not set
    initial stop = not set
    stop update = not set
    stop exit = not set

exit
    profit targets = not set
    signal exit = not set
    earnings exit = not set
    deadline = not set
    shared rules = not set
```

#### ORB (60-minute)

```text:surface
status
    state = disabled

market
    asset = not set
    market cap = not set
    average daily volume = not set
    market state = not set
    direction = not set

setup
    timeframe = 60-minute candles
    opening range = not set
    marks = not set
    volume = not set
    other filters = not set

entry
    window = not set
    long signal = not set
    short signal = not set
    order = not set
    earnings block = not set

risk
    position size = not set
    risk per trade = not set
    risk-to-reward ratio = not set
    R = not set
    initial stop = not set
    stop update = not set
    stop exit = not set

exit
    profit targets = not set
    signal exit = not set
    earnings exit = not set
    deadline = not set
    shared rules = not set
```

#### 20 SMA (4-hour)

```text:surface
status
    state = disabled

market
    asset = US stocks
    market cap >= $1 billion
    average daily volume >= 10 million shares
    market state = stock price is rising
    direction = long

setup
    timeframe = 4-hour candles only
    opening range = none
    marks = none
    price = candle close > SMA(20)
    other filters = none

entry
    window = next 4-hour candle open
    long signal = 4-hour candle close > SMA(20)
    short signal = none
    order = next 4-hour candle open if price remains above SMA(20)
    earnings block = none

risk
    position size = 10% of account
    risk per trade = not set
    risk-to-reward ratio = not set
    R = not set
    initial stop = not set
    stop update = not set
    stop exit = not set

exit
    profit targets = none
    signal exit = 4-hour candle falls below SMA(20)
    earnings exit = none
    deadline = none
    shared rules = none
```
