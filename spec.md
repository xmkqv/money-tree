---
name: money-tree
refs:
  - strategies = spec.strategies.md
vendors:
  - broker = alpaca
  - calendar = finnhub
  - engine = lumibot
  - host = railway
  - store = redis
elide:
  - http retries, pagination and rate limits
  - frame shaping and indicator arithmetic
  - logging
defer:
  - bot restarts and recovery
---

- the bot trades selected US-equity strategies on one broker account
- one daily loss limit ends the day for every strategy
- one risk budget sizes every entry
- the dashboard fits one display and says when it does not know
- every dashboard number leads to the trade behind it

# entities

| name | idea |
| --- | --- |
| asset | an instrument identified the same way across providers and ownership |
| bar | one open, high, low, close and volume over one span |
| feed | the source that supplies bars to a run |
| quote | the last price the broker reports for an asset |
| read | one vendor response and the instant it was taken |
| run | one bot process from start to finish |
| iteration | one pass of the portfolio loop |
| session | one exchange trading day from open to close |
| period | a span of sessions bounded in exchange time |
| baseline | the equity a period measures from |
| universe | the assets that pass price and turnover selection |
| signal | the condition that makes a strategy act |
| candidate | a proposed entry with price, stop and direction |
| order | one instruction sent to the broker |
| code | the frozen name that attributes an order to its strategy |
| fill | the part of an order the broker completed |
| exposure | the notional a position or holding places in the market |
| position | the exposure the broker reports |
| holding | the exposure a strategy manages, with stop and staged exits |
| ladder | the staged exits that reduce a holding |
| cap | the holding limit a strategy shares with the keys it counts |
| trade | one round trip from flat to flat |
| equity | the account value at one moment |
| snapshot | the realtime account, positions and open orders |
| ledger | trades, fills and profit over a period |
| levels | the prices a chart draws for entry and averages |
| state | the record the bot publishes for the dashboard |
| event | one dated note inside the published state |
| heartbeat | the time of the last publication |
| login | an authenticated web visitor |
| rules | the trading limits and strategy fields the bot and the web share |
| strategy | one named way to enter and manage holdings |
| family | strategies that share entry logic |
| variation | one configured member of a family |
| benchmark | the symbol every comparison uses |
| report | one backtest run and its artifacts |

# rules

- the bot and the web share rules; rules and state reject unknown fields
- each service alone receives its credentials, hosts and runtime limits
- lookback days count calendar days; lookback sessions count exchange sessions
- published rules omit secrets

```sh:surface
mt env list --service {web|bot}
```

# data

- vendor[broker] supplies account, positions, orders, fills, quotes, clock and asset permissions
- vendor[calendar] supplies common stocks and scheduled earnings
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

- partial exits accumulate into their trade; a reversal starts a new one
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
- a resting stop is an order at the broker; otherwise portfolio watches the stop
- resting-stop holdings exit before the session close
- Σ risk(open holdings) ≤ risk.per_day_max * equity
- count(holdings per cap) ≤ risk.positions_max / 2
- entry notional ≤ risk.notional_usd_max
- holding.stop never widens

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

enter(strategy, candidate, session)
    non-stock, unshortable short, paused strategy, held asset or quote through stop → skip
    pending included: positions ≥ risk.positions_max or gross exposure + entry > equity → skip

protect(holding)
    resting stop through quote → exit at market

iteration
    reconcile positions; check the daily loss; manage holdings; run strategies
    equity ≤ session open value * (1 - risk.per_day_max) →
        cancel orders; exit all; block entries for the day
        retry liquidation on later iterations
```

## strategy

- a strategy owns its signals and its holding management
- variations are specified in [strategies]

```py:surface
strategy
    key
    code
    family
    variation
    is_paused
    is_stop_resting
    cap → {own | family} keys

    entry_window(opens, closes) → (start, end)
    begin(session)
    run(session)
        capped → skip; candidates → portfolio.enter
    manage(holding, session)
        exits → portfolio.exit; stops → portfolio.protect
    ladder(holding, quantity) → ladder | none
```

# report

- a report runs the same portfolio, strategy and trade contracts as the bot
- a report funds an empty account with backtest.budget_usd
- asset defaults are simulation assumptions, not historical eligibility
- empty or non-stock assets fail before any artifact is written
- a report returns statistics, trades and plots against the benchmark
- a breakout report includes backtest.warm_up_days
- a daily report uses engine daily bars and does not establish fill fidelity

```sh:surface
mt report --strategy KEY --symbols SYM,… --start DATE --end DATE
```

# state

- state = status, selected and paused strategies, heartbeat, rules and bounded events
- status ∈ starting | running | stopped | failed
- one bot writer replaces `mt:state` every export interval, without expiry
- a vendor[store] publication failure warns; trading continues
- shutdown publication is best effort with a bounded wait
- a state read → absent | validated state; a failure stays an error
- the web keeps the last state across its own restarts and a stale heartbeat

# web

## access

- production login needs vendor[host] OAuth and an allowed email
- development login creates a local login
- a login cookie authenticates every route except the public ones
- unsafe methods on an authenticated route require X-CSRF-Token

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
# CSRF token and polling cadence

POST /logout
# end the login
```

## dashboard

- account, positions, orders and events fit one viewport; only the chart scrolls
- absent, stale and unavailable values render as such, never as zero
- a trade links to its chart
- trade marks rest clear of the candles and lead back to their price
- every response carries the read_at of its source
- snapshot and ledger share one account read
- an older response never replaces a newer account value

```http:surface
GET /api/strategies
# reported rules, otherwise configured rules
# selection: online | paused | unselected | unknown

GET /api/ledger
# orders, fills, profit, bot state, entry windows and limits
# gross loss is a positive magnitude
# stale when state is absent or the heartbeat is overdue

GET /api/snapshot
# realtime account, positions and open orders

GET /api/bars?symbol={symbol}&timeframe={timeframe}&opened={date}&closed={date}
# configured timeframes; symbol → asset; asset name accompanies the symbol
# stock hours follow exchange sessions; crypto and options use native hours

GET /api/levels?symbol={symbol}&strategy_key={key}&side={side}&entry={price}&opened={date}
# entry, stop and averages; non-stock → no equity strategy levels
```
