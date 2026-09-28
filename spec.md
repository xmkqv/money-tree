---
name: money-tree
refs:
  - spec:strategies = spec.strategies.md
vendors:
  - broker = alpaca
  - calendar = finnhub
  - engine = lumibot
  - filings = edgar
  - host = railway
  - store = redis
defer:
  - http retries, pagination and rate limits
  - frame shaping and indicator arithmetic
  - logging
---

- the bot trades selected US-equity strategies on one broker account
- one daily loss limit ends the day for every strategy
- one risk budget sizes every entry
- the dashboard fits one display
- the dashboard marks every value it does not know
- every dashboard number leads to the trade behind it

```sh:surface
mt env list --service {web|bot}
```

# entities

| name      | idea                                                                 |
|-----------|----------------------------------------------------------------------|
| asset     | an instrument with one identity across providers and ownership       |
| bar       | one open, high, low, close and volume over one span                  |
| feed      | the source that supplies bars to a run                               |
| quote     | the price of the latest trade the intraday feed reports for an asset |
| read      | one vendor response and its receipt instant                          |
| run       | one bot process from start to finish                                 |
| iteration | one pass of the portfolio loop                                       |
| session   | one exchange trading day from open to close                          |
| period    | a span of sessions bounded in exchange time                          |
| baseline  | the equity a period measures from                                    |
| portfolio | owns universe, sizing, exposure, ownership and execution for the bot |
| universe  | the assets that pass price and turnover selection                    |
| signal    | the condition that makes a strategy act                              |
| candidate | a proposed entry with price, stop and direction                      |
| order     | one instruction sent to the broker                                   |
| code      | the frozen name that attributes an order to its strategy             |
| fill      | the part of an order the broker completed                            |
| exposure  | the notional a position or holding places in the market              |
| position  | the exposure the broker reports                                      |
| holding   | the exposure a strategy manages, with stop and staged exits          |
| stop      | the price at which a holding exits                                   |
| ladder    | the staged exits that reduce a holding                               |
| target    | a price at which a ladder stage exits                                |
| cap       | the holding limit of one variation                                   |
| trade     | one round trip from flat to flat                                     |
| account   | the broker record the bot trades and the dashboard shows             |
| equity    | the account value at one moment                                      |
| snapshot  | the realtime account, positions and open orders                      |
| ledger    | trades, fills and profit over a period                               |
| levels    | the prices a chart draws for entry, stop, range and targets          |
| chart     | the bars, levels and marks the dashboard draws for one asset         |
| state     | the record the bot publishes for the dashboard                       |
| event     | one dated note inside the published state                            |
| heartbeat | the time of the last publication                                     |
| dashboard | the web page that fits one display                                   |
| login     | an authenticated web visitor                                         |
| rules     | the trading limits and strategy fields the bot and the web share     |
| strategy  | one named way to enter and manage holdings                           |
| family    | strategies that share entry logic                                    |
| variation | one configured member of a family                                    |
| window    | the span of a session in which a strategy enters                     |
| benchmark | the symbol every comparison uses                                     |
| report    | one backtest run and its artifacts                                   |

# data

- vendor[broker] supplies account, positions, orders, fills, quotes, clock and asset permissions
- vendor[calendar] supplies common stocks, industries and scheduled earnings
- vendor[filings] supplies annual gross profit and total assets per filer
- an earnings event date differs from its announcement date
- a run reads bars through one feed, ending at the engine clock

```py:surface
bars(assets, timeframe, start, end?) → {asset: [bar]}
    type ∉ {stock, crypto, option} → error before requesting
    time-ordered; missing → []; incomplete → error
    stock → configured daily or intraday feed, adjustment = all; otherwise native series
    explicit stock SIP end ≤ wall clock - bars.sip_delay_minutes

earnings(asset, date)
    non-stock → False
```

# trade

- partial exits add to their trade
- a reversal starts a new trade
- missing entry history → the entry time is unavailable
- periods: monday-to-date and month-to-date
- strategy totals, benchmark comparisons and equity selection share one period
- baseline = the last equity before the period, else the first equity inside it
- baseline ∈ {0, absent} → percentage unavailable

# bot

- vendor[engine] supplies lifecycle callbacks, order submission and fills
- paper and live both run through vendor[broker]

```sh:surface
mt trade --strategies KEY,…
```

## portfolio

- portfolio owns the universe, sizing, exposure, ownership and execution
- strategies reach bars, quotes and actions only through portfolio
- a stop never widens
- closing orders never exceed the broker position

```py:surface
universe
    active, tradable, fractionable stocks ∩ calendar common stocks
    price > universe.price_usd_min; turnover > universe.turnover_usd_min
    rank by turnover descending, symbol ascending

sizing(equity, price, stop_distance, direction)
    per_trade = risk.per_day_max / risk.positions_max
    allocation = 1 / risk.positions_max
    cap = risk.notional_usd_max / price
    quantity = min(equity * allocation / price, equity * per_trade / stop_distance, cap)
    short → whole shares; otherwise risk.quantity_decimal_places
    short with price > risk.notional_usd_max → 0
    quantity * price < risk.notional_usd_min → 0

quote(asset) → price | absent
    latest trade older than bars.trade_max_age_seconds → absent
    absent → the decision defers

enter(strategy, candidate, session)
    non-stock, unshortable short, paused strategy, held asset or quote through stop → skip
    pending included: positions ≥ risk.positions_max or gross exposure + entry > equity → skip

protect(holding)
    is_stop_resting → the stop is an order at the broker; otherwise portfolio watches the stop
    resting stop through quote → exit at market

iteration
    reconcile positions; check the daily loss; manage holdings; run strategies
    open orders without a position, holding or pending entry → cancel
    positions without a holding, pending entry or closing order → exit at market
    equity ≤ session open value * (1 - risk.per_day_max) →
        cancel orders; exit all; block entries for the day
        retry liquidation on later iterations
```

```md:invs
invs:
    Σ risk(open holdings) ≤ risk.per_day_max * equity
    entry notional ≤ risk.notional_usd_max
    count(holdings per cap) ≤ risk.positions_max / 2
```

## strategy

- a strategy owns its signals and its holding management
- [spec:strategies] declares the variations and logic

```py:surface
strategy
    key
    code
    family
    variation
    is_paused
    is_stop_resting

    symbols → fixed symbols outside the universe; daily frames include them
    entry_window(opens, closes) → (start, end)
    begin(session)
    prepare(now)
        after daily frames load, once per session
    run(session)
        capped → skip; candidates → portfolio.enter
    manage(holding, session)
        exits → portfolio.exit; stops → portfolio.protect
    ladder(holding, quantity) → ladder | none
```

# report

- a report runs the same portfolio, strategy and trade contracts as the bot
- asset defaults are simulation assumptions
- empty or non-stock assets fail before the report writes any artifact
- a report returns statistics, trades and plots against the benchmark
- daily fills are approximate

```py:surface
report(strategy, symbols, start, end)
    account = an empty account funded with backtest.budget_usd
    breakout → minute bars with backtest.warm_up_days of warm-up
    daily → engine daily bars
```

```sh:surface
mt report --strategy KEY --symbols SYM,… --start DATE --end DATE
```

# state

- a vendor[store] publication failure logs a warning
- trading continues after a publication failure
- shutdown publication waits a bounded time

```py:types
status ∈ {starting, running, stopped, failed}
state = (status, selected strategies, paused strategies, heartbeat, rules, events ≤ export.events_max)
```

```py:surface
publish(state)
    one bot writer; vendor[store].set("mt:state", state) every export.interval_seconds; no expiry
read() → absent | validated state
    failure → error
```

# web

## access

- production login needs vendor[host] OAuth and an allowed email
- development login creates a local login
- a login cookie authenticates every route except the public ones

```http:surface
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
# CSRF token, polling cadence and average colours

POST /logout
X-CSRF-Token: {token}
# end the login; every unsafe method on an authenticated route carries this header
```

## dashboard

- account, positions, orders and events fit one viewport
- only the chart scrolls
- absent, stale and unavailable values render as such, never as zero
- a trade links to its chart
- trade marks rest clear of the candles and lead back to their price
- an older response never replaces a newer account value
- the web keeps the last state across its own restarts

```http:surface
# every response carries the read_at of its source

GET /api/strategies → rules
# reported rules, otherwise configured rules

GET /api/ledger → ledger
# orders, fills, profit, bot state, entry windows and limits
# gross loss is a positive magnitude
# stale when state is absent or the heartbeat is overdue
# bot state gives the selection: online | paused | unselected | unknown

GET /api/snapshot → snapshot
# realtime account, positions and open orders; shares the ledger's account read

GET /api/bars?symbol={symbol}&timeframe={timeframe}&opened={date}&closed={date} → chart
# configured timeframes; symbol → asset; asset name accompanies the symbol
# stock hours follow exchange sessions; crypto and options use native hours

GET /api/levels?symbol={symbol}&strategy_key={key}&side={side}&entry={price}&opened={date} → levels
# range, stop and targets; non-stock → no equity strategy levels
```
