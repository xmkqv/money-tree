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
vendor[broker]: account, positions, orders, fills, quotes, clock
    vendor[engine] supplies simulated account data when backtesting

series = observations ordered by time
    realtime = current observations at the engine clock
    historical = earlier observations through the engine clock
    lookback = days or sessions of earlier data requested
    bars = vendor[broker] price and volume series
    account series = fills, closed orders, equity
    explicit stock SIP query end ≤ wall clock - bars.sip_delay_minutes

earnings = vendor[calendar] scheduled releases, including upcoming dates
    event date differs from announcement date
    historical announcement snapshots are not supplied
    earnings checks accept Asset
    non-stock → False without consulting the calendar

Asset = immutable {
    symbol, asset_type, expiration, strike, right,
    multiplier, leverage, precision, underlying_asset
}
    crypto identity includes quote currency in precision
    option identity includes expiration, strike, and right
    provider symbols preserve the complete pair or contract

permissions = {Asset: vendor[broker].Asset}
    active, tradable, fractionable
    broker metadata owns trading permissions
```

## historical bars

```py:surface
bars(assets, timeframe, start, end?, limit, pages_max?) → {Asset: [Bar]}
    bot and web share one fetcher
    group by asset_type; batch by bars.symbols_per_request
    options also respect bars.options_per_request

    stock → /v2/stocks/bars
        daily timeframe → bars.daily_feed
        otherwise → bars.intraday_feed
        adjustment = all
    crypto → /v1beta3/crypto/us/bars
    option → /v1beta1/options/bars
    crypto and options omit stock feed and adjustment

    missing observations → []
    unsupported asset_type → error before requesting
    follow pagination; remaining pages beyond pages_max → error
    bot converts observations to frames; web retains Bar records
```

## screening

```py:private
assets = {
    asset ∈ permissions:
    asset.asset_type = stock
    and asset.symbol ∈ vendor[calendar] common stocks
}
    price over screen.price_usd_min
    turnover over screen.turnover_usd_min
    order by turnover desc, symbol asc
```

# strategies

## identity and indicators

```py:types
strategy = {
    key = {family}_{variation} uq
    code uq frozen
    is_paused
    positions_max
    equity_risk_fraction_max
}

Candidate = { asset: Asset, price, stop, direction }
Position = { asset: Asset, strategy, direction, entry, stop, … }
    portfolio ownership and frame maps use complete Asset keys
    strings remain at provider and display boundaries

SMA ATR RSI ADX: period = indicators.period unless given
stop_distance = |entry - stop|
stop_fraction = stop_distance / entry
equity_risk_fraction_max = maximum fraction of equity risked per trade
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
    range = high and low across the first opening_minutes
    range.size < range_fraction_min * price → skip
    stop_distance / price ∉ [stop_fraction_min, stop_fraction_max] → skip
    volume to signal close < volume_multiple * its lookback_sessions mean → skip

    window = range close → min(session close, open + scan_minutes)
    signal = first close outside the range
    signal ∉ last signal_bars_max bars in window → skip
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
manage(position, bar)
    targets = target_multiples * stop_distance
    trail = trail_atr_multiple * ATR after trail_bars_min bars

    first target → set position stop = entry, then trail
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
    one entry per asset per session

    order = next open, else the next iteration enter allows
    stop = entry - stop_atr_multiple * ATR
```

### management

```py:surface
manage(position, session)
    set position stop = max(stop, highest close since entry - stop_atr_multiple * ATR)

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
    candidate.asset.asset_type ≠ stock → skip
    strategy.is_paused → skip
    positions ≥ risk.positions_max → skip
    exposure ≥ equity → skip
    asset held → skip
    short and (asset ∉ permissions or ¬permissions[asset].shortable) → skip
    quote through stop → skip

    quantity * stop_distance ≤ (strategy.equity_risk_fraction_max or risk.per_trade_max) * equity
    position ≤ risk.position_fraction_max * equity
```

## protection

```py:private
protect(position)
    long: stop ≥ last price → exit at market
    short: stop ≤ last price → exit at market
```

## daily loss limit

```py:private
cancel orders, exit all: vendor[engine] when backtesting, else vendor[broker]

cron:emergency_exit[portfolio.iteration_minutes]()
    equity ≤ session open value * (1 - risk.per_day_max) →
        cancel orders
        exit all
        end day
```

## backtest

```py:private
report(strategy, assets, start, end)
    CLI symbols are parsed into Assets
    empty assets or non-stock asset → error before creating artifacts
    permissions = simulated broker metadata using backtest.asset_defaults
    broker ids are generated; metadata is not fetched from today's catalogue
    positions = ∅
    equity = backtest.budget_usd

    bars = vendor[broker] minute bars after backtest.warm_up_days
    daily: vendor[engine] bars

    writes stats, trades, plots vs benchmark_symbol
```

# bot state

```sketch
bot ──SET mt:state──→ redis ←──GET mt:state── web
```

```py:types
state = {
    status ∈ starting|running|stopped|failed
    strategies
    paused
    heartbeat_at
    configuration
    events ≤ export.events_max
}
```

```py:surface
redis.url: required RedisDsn, shared by bot and web
state key = "mt:state"
    latest state JSON
    no expiry
    one bot writer; each SET replaces the previous value

publish_state(client, state)
    client.SET(state key, state JSON)

async read_state(client)
    raw = await client.GET(state key)
    absent → None
    otherwise → validated state
    connection or validation failure → error
    accepts optional legacy run_id, sequence, started_at with their original value constraints
    legacy fields are excluded from writes; all other unknown fields are rejected
```

```py:private
bot:
    owns synchronous client in exporter thread
    publishes events and heartbeat per export.interval_seconds
    RedisError → warn and continue
    trade joins exporter ≤ export.close_timeout_seconds
    final publication is best effort

web:
    owns asynchronous client in application lifespan
    closes client on shutdown
    reads persisted state after restart

deployment:
    activate compatible web reader and retire old readers before deploying reduced bot writer
    initial rollout uses separate deployments; build completion is not reader readiness
    rollback restores old writer and full record before old readers
    retain legacy read fields until old writers are retired and stored state omits them
```

# web

- the whole account reads on one screen without scrolling
- the dashboard says when it does not know
- every number leads to the trade or rule behind it

## access

```py:surface
public:
    GET /healthz
    GET /login
    GET /auth/callback

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
    state.configuration when reported; otherwise configured rules

GET /api/ledger
    current orders, fills, P&L
    bot state from Redis
    stale = state absent
        or now - state.heartbeat_at > web.heartbeat_timeout_seconds
    retain reported state when stale

GET /api/pulse
    realtime account, positions, open orders

GET /api/bars
    historical bars by timeframe ∈ dashboard.chart_timeframes
    query symbol → complete Asset
    stock hourly bars → equity-session aggregation
    crypto and option hourly bars → native hourly observations
    response fields remain unchanged

GET /api/levels
    marks and averages at an entry
    non-stock → no equity strategy levels
```


### terminology and trade data

- strategy records use `key`; references to a strategy key use `strategy_key`
- price observations are bars; selected intervals are timeframes
- sequence offsets use `index`; holdings remain positions
- entry display components derive from `entered_at` in exchange time
- fractional P&L and percentage P&L remain distinct
- renamed application fields and configuration keys replace previous names together

```py:types
Trade = {
    symbol, side, strategy_key, quantity, entry, exit, pnl
    date, minute = exit components in exchange time
    entered_at = timezone-aware ISO timestamp of first entry fill
    duration_minutes = max(0, floor(elapsed seconds / 60))
    fills = [{ d, m, p, quantity, s }]
}
OpenTrade = { strategy_key, entered_at, fills }
    current positions without entry history: entered_at = null

Totals = { n, wins, losses, gross_profit, gross_loss, net_pnl }
    gross_profit = sum(positive trade pnl)
    gross_loss = abs(sum(nonpositive trade pnl))
    net_pnl = sum(trade pnl)

unrealized_pnl = unrealized profit or loss in account currency
unrealized_pnl_fraction = vendor[broker].unrealized_plpc
unrealized_pnl_percent = 100 * unrealized_pnl_fraction

strategy selection state ∈ online|paused|unselected|unknown
unattributed strategy label = "Unattributed"
TC_STATE.timeframe = selected chart interval
```

```py:surface
match_trades(fills, orders, flat_quantity_max) → trades, open_trades
    a trade spans flat position → entry fills → exit fills → flat position
    partial exits accumulate until flat; a reversal starts a new trade
    entered_at comes from the original fill timestamp, including its offset
```

### calendar periods

week = monday-to-date, anchored to the current exchange date
month = calendar-month-to-date, anchored to the current exchange date
strategy totals, benchmark comparisons, equity selection → use the same boundaries
baseline = last available observation strictly before the boundary
funded within period → first available observation
zero or missing baseline → percentage unavailable
