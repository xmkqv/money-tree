---
name: money-tree
vendors:
  broker: alpaca
  calendar: finnhub
  engine: lumibot
  host: railway
---

- the bot trades the selected strategies against one broker account
- one daily loss limit ends the trading day across every strategy
- a report replays one strategy over a date range into one run directory
- the dashboard shows an allowed user the account, orders, fills, and the bot heartbeat
- one command pushes both services to one revision

```sh:surface
mt trade --strategies KEY,…
mt report --strategy KEY --symbols SYM,… --start DATE --end DATE
mt env list --service {web|bot}
```

```sketch
┌─────────┐  signed snapshot  ┌─────────┐  session cookie  ┌─────────┐
│   bot   ├──────────────────→│   web   │←─────────────────┤ browser │
└────┬────┘                   └────┬────┘                  └─────────┘
     │ orders quotes bars          │ account orders fills bars
     ↓                             ↓
vendor[broker]                 vendor[broker]
```

```text:types
live = the account as vendor[broker] holds it now: equity, cash, positions, orders, fills, quotes, listing
past = completed bars from vendor[broker] and earnings dates from vendor[calendar], read up to an instant
listing = which symbols vendor[broker] trades, with fractions and shorts
turnover = session close * volume
market = vendor[calendar]'s common stocks in the listing clearing the screen floors on price and turnover, by turnover, highest first
replay = a run against vendor[engine]'s simulated account
```

```sketch
mise.toml             shared configuration
 └─→ mise.{env}.toml  every variable its services read
      └─→ .env.{env}  a secret's value
         └─→ settings load once, typed
```

- `mise*.toml` owns every configuration value
- a secret is named under `[vars]` in `mise.{env}.toml`
- neither environment inherits a value from the other
- a missing variable crashes the service

# layers

- one distribution, `mt`, holds every module
- a package names what its modules know, never where they run
- nothing imports `cli`, `bot`, or `web`
- `data` alone speaks a vendor wire
- a service builds its clients at start-up
- `snapshot` is the contract between `bot` and `web`

```sketch
cli   bot ──→ snapshot ←── web
 │     │ ┌───────┘
 ↓     ↓ ↓
strategies ──→ data ──→ config
signals        reads    variable
```

# strategies

- a strategy is one class under `strategies/`, inheriting from base
- a strategy key is `{family}_{variation}`, and its names derive from the key
- the registry rejects a strategy whose key or order-tag code is undeclared or taken
- the one-character order-tag code is frozen wire format, never re-used
- a strategy owns whether it is paused, its position cap, and its risk fraction
- a strategy setting is keyed by its family when shared, else by its key
- a paused strategy opens no position and runs its holdings to their exits

```text:types
R = |entry price - initial stop|
range(p) = opening range low + p * opening range size
SMA(n), ATR(n), RSI(n), ADX = standard indicators over n candles, n = the indicator period unless stated
iteration = one pass of every strategy, each iteration minutes
rescan = the candidates of the day are offered again on every iteration to the close
```

## breakout

```text:surface
setup(session)
    opening range = the first candle of the session, its length the variation's opening minutes
    marks = range high, range(mid), range low
    inv:range size < its floor fraction of price → skip
    inv:initial stop distance ∉ the family's fraction band of price → skip
    inv:cumulative volume at the signal candle close < the variation's volume multiple
        * the average at the same time of day over the past sessions → skip

entry(candle)
    window = the opening range close to the open plus the scan minutes
    long signal = first close above range high · short signal = first close below range low
    inv:signal candle ∉ the last completed candles within the window → skip
    inv:entry beyond the range > the entry extension * range size, when the variation sets one → skip
    inv:live quote already through the initial stop → skip
    inv:breakout positions ≥ the family cap → skip
    order = open of the next candle
    long stop = range(long stop fraction) · short stop = range(short stop fraction)

exit(candle)
    target step = a target multiple of R
    trail = the trail multiple * ATR on strategy candles across sessions, once the minimum candles complete
    first target step → set stop = breakeven, then trail
    each target step → close its target fraction, rounded down to a whole share; a leg under one share is skipped
    the stop never moves back
    a lead time before the session close → close the remainder
```

## daily

|          | daily_sma                                                                 | daily_tfb                                            |
|----------|---------------------------------------------------------------------------|------------------------------------------------------|
| turnover |                                                                           | over its turnover sessions                           |
| trend    | price > SMA(trend) > SMA(long trend)                                      | price > SMA(trend) > SMA(trend) its lag sessions ago |
| momentum | RSI ≥ its floor and ADX ≥ its floor                                       | ADX ≥ its floor                                      |
| signal   | day 1 close < SMA(average sessions); day 2 close above it and above day 1 | close > previous candle high                         |

```text:surface
market state = the benchmark symbol > SMA(average sessions)
direction = long

entry(session)
    inv:¬market state → skip
    inv:heeding earnings and an earnings date within the block days → skip
    window = session open to close, rescan
    order = the next open, or the first later iteration with a free slot and free money
    one entry per symbol per session
    stop = entry - its ATR multiple * ATR

exit(session)
    set stop = max(stop, highest close since entry - its ATR multiple * ATR)
    daily close < stop → exit at the next open
    daily close < SMA(average sessions) or RSI < its exit ceiling → exit at the next open
    heeding earnings → exit the day before an earnings date
```

# portfolio

```text:surface
positions ≤ the account cap across strategies
gross exposure < equity, else the entry is skipped
position fraction ≤ the position fraction cap
risk per trade = its risk fraction of equity at entry, else the account risk cap
one strategy owns a symbol at a time
a stop order at or beyond the last price goes at market

emergency exit
    session baseline = portfolio value at the session's first iteration
    inv:equity ≤ session baseline * (1 - the daily loss cap)
        → cancel open orders, exit every holding, end the day
```

# snapshot

```text:types
snapshot = { run_id, sequence, status, strategies, paused, started_at, heartbeat_at, configuration, events capped }
status = starting | running | stopped | failed
```

```sketch
bot                        web                          browser
 ├──snapshot starting──────→│                            │
 ├──snapshot running───────→│                            │
 ├──snapshot heartbeat_at──→│  every export interval     │
 │                          │←──GET /api/ledger──────────┤
 │                          ├──bot state────────────────→│
 │   no heartbeat within    │                            │
 │   the heartbeat timeout  │←──GET /api/ledger──────────┤
 │                          ├──stale────────────────────→│
 ├──snapshot stopped───────→│                            │
```

# bot

```text:private
trade(strategies)
    publish starting → run vendor[engine] → publish running
    SIGTERM → stop all → publish stopped · failure → publish failed

cron:export[the export interval]()
    POST the signed snapshot to web

backtest(strategy, symbols, start, end) → runs/{strategy}-{start}-{end}/
    market = the given symbols
    quote = vendor[broker] minute bars after the warm-up for breakout, vendor[engine]'s daily bars for daily
    equity = the backtest budget
    writes vendor[engine] stats, trades, settings, log, and plots against the benchmark symbol
```

- the engine answers live from vendor[broker] when trading and from its simulation when replaying
- listing, positions, and tagged orders come from vendor[broker] directly
- a replay lists every given symbol and holds nothing
- every past read is bounded by the engine clock, never the wall clock

# web

```text:surface
GET  /healthz              public
GET  /login                public · development → local session · production → vendor[host] oauth
GET  /auth/callback        production · email ∉ the allowed emails → 403
POST /internal/state       public · signature within the signature window, else 401
                           · body within the body limit, else 413 · body parses, else 422
                           · sequence newer than the last, else 409
POST /logout               clears the session and site data
GET  /                     dashboard
GET  /assets/{file}        immutable
GET  /api/session          csrf token, browser poll cadence
GET  /api/strategies       each strategy's rules as it will trade today
GET  /api/ledger           live orders, fills, P&L · snapshot bot state
GET  /api/pulse            live · account, positions, open orders
GET  /api/bars             past · symbol, timeframe ∈ the chart timeframes, opened, closed
GET  /api/levels           past · symbol, strategy, side, entry, opened → opening range marks and averages
```

- every route outside the public paths needs a session cookie
- an unsafe method also needs the `X-CSRF-Token` header
- each read response carries its own server cache, browser max-age, and browser poll cadence
- a bars or levels response is cached per query, under a bounded key count
- the bot is stale when no heartbeat arrives within the heartbeat timeout
- a vendor[broker] 429 becomes 503 with Retry-After
- any other upstream error becomes 502

# deploy

- vendor[host] runs one project of two services: web serves the dashboard, bot runs the trader
- the bot reaches web over the project's private endpoint
- web is healthy when `/healthz` answers
- deploying sets every variable a service reads before shipping
