---
name: money-tree
vendors:
  broker: alpaca
  calendar: finnhub
  engine: lumibot
  host: railway
defer:
  - persisted state
  - restarts and recovery
---

- the bot trades the selected strategies on one broker account
- one daily loss limit ends the day for every strategy
- fractional positions are supported

```sh:surface
mt trade --strategies KEY,…
mt report --strategy KEY --symbols SYM,… --start DATE --end DATE
mt env list --service {web|bot}
```

# data

## sources

```py:types
live = account, positions, orders, fills, quotes, listing
    vendor[engine] answers when replaying

past = vendor[broker] bars ∪ vendor[calendar] earnings
    up to the engine clock

listing = {
    symbols
    shorts ⊆ symbols
}
```

## screening

```py:private
symbols = vendor[calendar] stocks ∩ listing.symbols
    price over screen.price_usd_min
    turnover over screen.turnover_usd_min
    order by turnover desc
```

# strategies

## identity and indicators

```py:types
strategy = {
    key = {family}_{variation} uq
    code uq frozen
    is_paused
    positions_max
    risk_fraction_max
}

SMA ATR RSI ADX: period = indicators.period unless given
R = |entry - stop|
```

## breakout

### range

```py:types
range(p) = range.low + p * range.size
marks = range(0), range(mid_fraction), range(1)
```

### entry

```py:surface
run(session)
    range = first opening_minutes candle
    range.size < range_fraction_min * price → skip
    R / price ∉ [stop_fraction_min, stop_fraction_max] → skip
    volume to signal close < volume_multiple * its past_sessions mean → skip

    window = range close → open + scan_minutes
    signal = first close outside the range
    signal ∉ last signal_candles_max candles in window → skip
    when entry_extension_max is set:
        long: entry > range.high + entry_extension_max * range.size → skip
        short: entry < range.low - entry_extension_max * range.size → skip
    quote through stop → skip
    family positions ≥ positions_max → skip

    order = next open
    stop =
        long: range(long_stop_fraction)
        short: range(short_stop_fraction)
```

### management

```py:surface
manage(holding, candle)
    targets = target_multiples * R
    trail = trail_atr_multiple * ATR after trail_candles_min candles

    first target → set holding stop = entry, then trail
    stop never moves back
    each target → close its target_fractions share
partial short targets → round down to whole shares; skip zero-share slices
final target → close the remainder
    close_lead_minutes before close → close the rest
```

## daily

### signals

```py:surface
is_market_favorable = benchmark close > SMA(average_sessions)

daily_sma =
    price > SMA(trend_sessions) > SMA(trend_sessions_long)
    and RSI ≥ rsi_min
    and ADX ≥ adx_min
    and close crosses above SMA(average_sessions)
    and close[-1] > close[-2]

daily_tfb =
    turnover over turnover_sessions
    and price > SMA(trend_sessions) rising over trend_lag_sessions
    and ADX ≥ adx_min
    and close > previous high
```

### entry

```py:surface
run(session)
    ¬is_market_favorable → skip
    when does_heed_earnings:
        earnings within earnings.block_days → skip

    window = open → close
    cadence = portfolio.iteration_minutes
    one entry per symbol per session

    order = next open, else the next iteration enter allows
    stop = entry - stop_atr_multiple * ATR
```

### management

```py:surface
manage(holding, session)
    set holding stop = max(stop, highest close since entry - stop_atr_multiple * ATR)

    exit at next open when:
        close < stop
        or close < SMA(average_sessions)
        or RSI < exit_rsi_max
        or at the open of the last exchange session strictly before earnings, when heeded
    weekend and holiday earnings → use the last preceding exchange session
    retry during that session until an exit is submitted
```

# bot

## entry limits

```py:private
enter(strategy, candidate, session)
    strategy.is_paused → skip
    positions ≥ risk.positions_max → skip
    exposure ≥ equity → skip
    symbol held → skip
    quote through stop → skip

    risk = (strategy.risk_fraction_max or risk.per_trade_max) * equity
    position ≤ risk.position_fraction_max * equity
```

## protection

```py:private
protect(holding)
    long: stop ≥ last price → exit at market
    short: stop ≤ last price → exit at market
```

## daily loss limit

```py:private
cron:emergency_exit[portfolio.iteration_minutes]()
    equity ≤ session open value * (1 - risk.per_day_max) →
        cancel orders
        exit all
        end day
```

## replay

```py:private
report(strategy, symbols, start, end)
    listing.symbols = symbols
    positions = ∅
    equity = backtest.budget_usd

    candles = vendor[broker] minute bars after backtest.warm_up_days
    daily: vendor[engine] bars

    writes stats, trades, plots vs benchmark_symbol
```

# web

## bot state

```sketch
bot ──private signed snapshot per export.interval_seconds──→ web
```

```py:types
snapshot = {
    run_id
    sequence
    status ∈ starting|running|stopped|failed
    strategies
    paused
    started_at
    heartbeat_at
    configuration
    events ≤ export.events_max
}
```

```py:surface
POST /internal/state
    reject when:
        stale signature
        or body > web.state_body_bytes_max
        or invalid snapshot
        or sequence ≤ last within the same run_id
```

## access

```py:surface
public:
    GET /healthz
    GET /login
    GET /auth/callback
    POST /internal/state

others need a session cookie
unsafe session-authenticated methods: X-CSRF-Token

GET /login → /auth/callback
    development: local session
    production:
        vendor[host] oauth
        email ∉ login.allowed_emails → reject

POST /logout
GET /api/session → csrf token, poll cadence
```

## dashboard

```py:surface
GET / → dashboard

GET /api/strategies
    today's rules per strategy

GET /api/ledger
    live orders, fills, P&L
    bot state, stale after web.heartbeat_timeout_seconds

GET /api/pulse
    live account, positions, open orders

GET /api/bars
    past bars by timeframe ∈ dashboard.chart_timeframes

GET /api/levels
    marks and averages at an entry
```


### calendar periods

week = monday-to-date, anchored to the current exchange date
month = calendar-month-to-date, anchored to the current exchange date
strategy totals, benchmark comparisons, equity selection → use the same boundaries
baseline = last available observation strictly before the boundary
funded within period → first available observation
zero or missing baseline → percentage unavailable
