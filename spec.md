---
name: money-tree
vendors:
  broker: alpaca
  calendar: finnhub
  engine: lumibot
  host: railway
  state: redis
defer:
  - trading restarts and recovery
---

- the bot trades selected US-equity strategies on one broker account
- one daily loss limit ends the day for every strategy
- fractional positions are supported
- the whole account reads on one screen without scrolling
- the dashboard says when it does not know
- every number leads to the trade or rule behind it

```sh:surface
mt trade --strategies KEY,…
mt report --strategy KEY --symbols SYM,… --start DATE --end DATE
mt env list --service {web|bot}
```

# configuration

bot and web share validated trading rules.
service configuration owns credentials and runtime settings.
unknown nested fields fail validation.
published rules omit secrets.

# data

vendor[broker] supplies account, positions, orders, fills, quotes and clock.
broker metadata owns trading permissions.
vendor[calendar] supplies common stocks and scheduled earnings.
earnings event dates differ from announcement dates.

asset identity is immutable across providers and ownership.
crypto identity includes base and quote.
option identity includes underlying, expiration, strike and right.

```py:surface
bars(assets, timeframe, start, end?) → {Asset: [Bar]}
    type outside stock | crypto | option → error before requesting
    observations are time-ordered
    missing → []
    incomplete retrieval → error
    stock: configured daily or intraday feed, adjustment = all
    crypto and option: native series without stock feed or adjustment
    explicit stock SIP end ≤ wall clock - bars.sip_delay_minutes

earnings(asset, date)
    non-stock → False without consulting the calendar
```

historical bot observations end at the engine clock.

# bot

## portfolio

portfolio owns screening, exposure, ownership and execution.
strategies obtain observations and actions through portfolio.

```py:surface
screen
    active, tradable, fractionable stocks ∩ calendar common stocks
    price > screen.price_usd_min; turnover > screen.turnover_usd_min
    rank by turnover descending, symbol ascending

enter(strategy, candidate, session)
    non-stock, paused strategy, held asset or quote through stop → skip
    short without broker shortable permission → skip
    positions including pending ≥ risk.positions_max → skip
    quantity * stop distance ≤ (strategy risk override or risk.per_trade_max) * equity
    position notional ≤ risk.position_fraction_max * equity
    gross exposure including pending and new entry ≤ equity

protect(position)
    resting stop through last price → exit at market

iteration
    reconcile positions; check daily loss; manage positions; run selected strategies
    equity ≤ session open value * (1 - risk.per_day_max) →
        cancel orders; exit all; block entries for the day
        retry liquidation on subsequent iterations
```

## strategies

strategies own signals and position management.
frozen unique codes attribute orders.

### breakout

```py:surface
entry
    range = opening high and low
    marks = low, configured midpoint, high
    range width / price below minimum → skip
    stop distance / price outside configured bounds → skip
    volume to signal close below configured multiple of historical mean → skip
    window = range close → min(session close, open + scan_minutes)
    signal = first close outside range, within configured recent bars
    entry extension beyond configured fraction of range, when set → skip
    family position cap reached → skip
    enter at next open
    stop = configured long or short fraction above range low

management
    targets = configured multiples of initial stop distance
    each target → close configured share; final target → close remainder
    partial short exits round down to whole shares; zero → skip
    first target → stop at entry; then trail by configured ATR multiple
    trailing requires configured minimum bars
    stop never moves back
    configured lead before session close → close remainder
```

### daily

```py:surface
signals
    daily_sma = price > SMA(trend_sessions) > SMA(trend_sessions_long)
        and RSI ≥ rsi_min and ADX ≥ adx_min
        and close crosses above SMA(average_sessions) and close[-1] > close[-2]
    daily_tfb = turnover over turnover_sessions
        and price > SMA(trend_sessions) rising over trend_lag_sessions
        and ADX ≥ adx_min and close > previous high

entry
    benchmark close ≤ SMA(average_sessions) → skip
    heeded earnings within configured window → skip
    strategy position cap reached → skip
    one entry per asset per session, between open and close
    enter at next open, else next permitted iteration
    stop = entry - stop_atr_multiple * ATR

management
    stop = max(stop, highest close since entry - stop_atr_multiple * ATR)
    close < stop or close < SMA(average_sessions) or RSI < exit_rsi_max → exit at next open
    heeded earnings → exit at open of last exchange session strictly before earnings
    retry earnings exit until submitted
```

## execution

vendor[engine] supplies lifecycle callbacks, order submission and partial or final fills.
paper and live use vendor[broker].
reports simulate execution under the same portfolio and strategy contracts.

reports start with an empty account funded by backtest budget.
asset defaults are independent of today's catalogue.
results include statistics, trades and plots against the benchmark.
empty or non-stock assets fail before artifact creation.
breakout reports include warm-up.

# state

state = status (starting | running | stopped | failed), selected and paused
strategies, heartbeat, configuration, bounded events.
unknown fields fail validation.

one bot writer replaces validated JSON at `mt:state` every export interval.
state has no expiry.
vendor[state] publication failure warns without stopping trading.
shutdown publication is best effort with bounded wait.
reads return absent or validated state.
read failures remain errors.
web retains persisted state across restarts and stale heartbeats.

# web

## access

production login requires vendor[host] OAuth and an allowed email.
development login creates a local session.

session cookies authenticate all routes except the public routes below.
unsafe session-authenticated methods require X-CSRF-Token.

```http
GET /healthz
# public

GET /login
# public

GET /auth/callback?code={code}&state={state}
# public; production only

GET /
# dashboard

GET /assets/{filename}
# static asset

GET /api/session
# CSRF token and polling cadence

POST /logout
# end session
```

## dashboard

```http
GET /api/strategies
# reported rules, otherwise configured rules
# selection: online | paused | unselected | unknown

GET /api/ledger
# orders, fills, P&L, bot state
# gross loss is a positive magnitude
# stale when state is absent or heartbeat overdue

GET /api/pulse
# realtime account, positions, open orders

GET /api/bars?symbol={symbol}&timeframe={timeframe}&opened={date}&closed={date}
# configured timeframes; symbol → Asset
# stock hours follow equity sessions; crypto and options use native hours

GET /api/levels?symbol={symbol}&strategy_key={key}&side={side}&entry={price}&opened={date}
# entry marks and averages; non-stock → no equity strategy levels
```

pulse and ledger share account observations.
dashboard responses include source read_at.
older responses cannot replace newer account values.

## trades

trades span flat to flat.
partial exits accumulate.
reversals start a new trade.
missing entry history → entry time unavailable.

calendar periods use exchange time: monday-to-date and calendar-month-to-date.
strategy totals, benchmark comparisons and equity selection share boundaries.
percentage baseline = last observation before boundary,
    or first available when funded within period.
zero or missing baseline → percentage unavailable.
