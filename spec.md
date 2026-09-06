---
name: money-tree
vendors:
  broker: alpaca
  engine: lumibot
  host: railway
---

- the bot trades the selected strategies against one broker account
- a paused strategy opens no position and runs its holdings to their exits
- one daily loss limit ends the trading day across every strategy
- a report replays one strategy over a date range and writes one run directory
- the dashboard shows an allowed user the account, orders, fills, and the bot heartbeat
- one command pushes both services to one revision

```sh:surface
mt trade --strategies KEY,…
mt backtest --strategy KEY --symbols SYM,… --start DATE --end DATE
mt report --strategy KEY --symbols SYM,… --start DATE --end DATE
mt env list --service {web|bot}
```

```sketch
┌───────┐  signed snapshot   ┌───────┐  cookie session  ┌─────────┐
│  bot  │ ─────────────────→ │  web  │ ←─────────────── │ browser │
└───┬───┘                    └───┬───┘                  └─────────┘
    │ live: orders · quotes      │ live: account, orders, fills
    │ past: bars                 │ past: bars
    ↓                            ↓
vendor[broker]               vendor[broker]
```

```text:types
live ≔ the account as vendor[broker] holds it now: equity, cash, positions, orders, fills, quotes, listing
past ≔ what the market already did: completed bars, the index, earnings dates, read up to an instant
listing ≔ which symbols vendor[broker] trades, fractions, and shorts
screen ≔ today's market clearing the universe floors; runs only when trading
replay ≔ a run against vendor[engine]'s simulated account
```

- `mise*.toml` owns every configuration value; this spec names roles, never keys and never numbers
- `mise.{env}.toml` declares every variable its services read
- a variable declared empty is a secret and lives in `.env.{env}`
- neither environment inherits a value from the other
- settings load once, typed, and a missing variable crashes the service

# layers

- one distribution, `mt`, holds every module
- a package names what its modules know, never where they run
- `bot`, `web`, and `cli` are the three services; nothing else imports them
- `config` declares every variable, `data` holds every outside read, `strategies` holds the signals
- `data` is the only module that speaks a vendor wire; a service builds its clients at start-up
- `snapshot` is the contract between `bot` and `web`

```sketch
cli · bot · web  →  snapshot  →  strategies  →  data  →  config
                                      ↓           ↓        ↓
                        exchange · frames · indicators · position
```

# strategies

- a strategy is one class in one module under `strategies/`, inheriting from base
- a strategy key is `{family}_{variation}`; its display name and class name derive from that key
- the registry rejects a strategy whose key, order-tag code, or position disagrees with the key type
- the one-character order-tag code is frozen wire format, assigned once and never re-used
- a strategy owns whether it is paused, its position cap, and its risk per trade
- a strategy setting is keyed by the family it is shared by, or by the key that owns it
- a stop at or beyond the last price closes the position at market

```text:types
ET ≔ US Eastern Time
account ≔ account value when the position opens
R ≔ |entry price − initial stop|
range(p) ≔ opening range low + p · opening range size
SMA(n), ATR(n), RSI(n), ADX ≔ standard indicators over n candles, n ≔ the indicator period unless stated
whole shares ≔ each leg rounds down to a whole share; a slice under one share is skipped
rescan ≔ the candidates of the day are offered again on every iteration to the close
market ≔ US stocks clearing the universe floors on market cap, share price, and daily turnover
sorting ≔ last completed session close · volume, highest first, when candidates exceed room
position size ≔ the position fraction cap of account
```

## breakout

- Breakout 5m and Breakout 10m share one surface and differ only in their settings

```text:surface
setup
    opening range ≔ the first candle of the session, its length the variation's opening minutes
    marks ≔ range high, range(mid), range low
    range size ≥ its floor fraction of price
    initial stop distance ∈ the family's fraction band of price
    cumulative volume ≥ the variation's volume multiple · the average at the same time of day
        over the past sessions, read at the signal candle close

entry
    long signal ≔ first close above range high · short signal ≔ first close below range low
    signal candle ∈ the last completed candles, within the family's signal window
    window ≔ the opening range close to the open plus the scan minutes
    order ≔ open of the next candle
    max entry beyond the range ≔ the entry extension · range size, when the variation sets one
    entry block ≔ live quote already through the initial stop
    breakout positions ≤ the family cap across both variations

risk
    risk per trade ≔ the variation's risk fraction
    long stop ≔ range(long stop fraction) · short stop ≔ range(short stop fraction)
    trail ≔ the trail multiple · ATR on strategy candles across sessions,
        once the minimum candles complete
    the active stop never moves past breakeven into a loss

exit
    breakeven and trail at the first target step
    close 50% / 25% / 25% at the three target steps
    close any remainder a lead time before the session close
```

## daily

|          | Daily SMA                                                                    | Daily TFB                                                            |
|----------|------------------------------------------------------------------------------|----------------------------------------------------------------------|
| turnover | daily                                                                        | over its turnover sessions                                           |
| trend    | price > SMA(trend) > SMA(long trend)                                         | price > SMA(trend) > SMA(trend) its lag sessions ago                 |
| momentum | RSI ≥ its floor and ADX ≥ its floor                                          | ADX ≥ its floor                                                      |
| signal   | day 1 close < SMA(average sessions); day 2 close above it and above day 1    | close > previous candle high                                         |
| order    | day 3 open                                                                   | next open                                                            |
| stop     | highest close since entry − its ATR multiple · ATR                           | entry − its ATR multiple · ATR, then highest close since entry − the same |

```text:surface
market state ≔ SPX > SMA(average sessions) · direction ≔ long

entry
    window ≔ market open to close, rescan
    order ≔ the signal open, or the first later iteration with a free slot and free money
    one entry per symbol per session
    positions ≤ its position cap · risk per trade ≔ its risk fraction
    heeding earnings → no entry within the block days before a report, exit the day before

risk
    the stop recalculates daily and only moves up
    a daily close below the stop exits at the next open

exit
    signal exit ≔ daily close < SMA(average sessions) or RSI under its exit ceiling
    shared rules ≔ stop loss, emergency exit
```

## portfolio

```text:surface
positions ≤ the account cap across strategies · an entry is skipped when gross exposure ≥ equity
position fraction ≤ the position fraction cap
risk per trade ≤ the account risk cap unless the strategy sets its own

emergency exit
    session baseline ≔ portfolio value at the session's first iteration
    equity ≤ session baseline · (1 − the daily loss cap) → cancel open orders,
        exit every holding, lock the day
```

# bot

```text:private
trade(strategies)
    exporter ≔ signed snapshot publisher for the web export endpoint
    publish starting → run vendor[engine] → publish running
    SIGTERM → stop all → publish stopped · failure → publish failed

cron:export[the export interval]()
    POST {run_id, sequence, status, strategies, paused, started_at, heartbeat_at,
          configuration, events capped}

backtest(strategy, symbols, start, end)
    universe ≔ the given symbols
    quote ≔ vendor[broker] minute bars after the warm-up for breakout · Yahoo daily bars for daily
    past ≔ as when trading, bounded by the engine clock
    budget ≔ the backtest budget · benchmark ≔ the benchmark symbol

report(strategy, symbols, start, end) → runs/{strategy}-{start}-{end}/
    ≔ backtest written to one directory of vendor[engine] stats, trades, settings, log, and plots
```

- the book reads live through vendor[engine]; the engine answers from vendor[broker] when trading and from its simulation when replaying
- listing is the one live read outside the engine; a replay lists every given symbol
- every past read is bounded by the engine clock, never the wall clock
- a replay's universe is its given symbols; the screen never runs inside a replay
- a live-wire field is never read off an engine entity

# web

```text:surface
GET  /healthz              public
GET  /login                public · development → local session · production → vendor[host] oauth
GET  /auth/callback        production · email ∉ the allowed emails → 403
POST /internal/state       public · signature within the signature window,
                           body within the body limit, else 401 · 413 · 422
POST /logout               clears the session and site data
GET  /                     dashboard
GET  /assets/{file}        immutable
GET  /api/session          csrf token, browser poll cadence
GET  /api/strategies       each strategy's rules as it will trade today
GET  /api/ledger           live · orders, fills, P&L, bot state
GET  /api/pulse            live · account, positions, open orders
GET  /api/bars             past · symbol, timeframe ∈ {5Min, 1Hour, 1Day}, opened, closed
GET  /api/levels           past · symbol, strategy, side, entry, opened → opening range marks and averages
```

- every route outside the public paths needs a session cookie
- an unsafe method also needs the `X-CSRF-Token` header
- each read response carries its own server cache, browser max-age, and browser poll cadence
- a bars or levels response is cached per query, under a bounded key count
- the bot is stale when no heartbeat arrives within the heartbeat timeout
- a vendor[broker] 429 becomes 503 with Retry-After; any other upstream error becomes 502

# deploy

- vendor[host] runs one project of two services: web serves the dashboard, bot runs the trader
- the bot reaches web over the project's private endpoint
- web is healthy when `/healthz` answers
- deploying sets every variable a service reads, then ships both services at one revision

---

# refs

- vendor[engine] ≔ [lumibot](https://github.com/Lumiwealth/lumibot#quick-start)
