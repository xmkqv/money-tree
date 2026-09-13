---
name: money-tree
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
  - trading restarts and recovery
---

- the bot trades selected US-equity strategies on one broker account
- one daily loss limit ends the day for every strategy
- one risk budget sizes every entry
- fractional positions are supported
- the whole account reads on one display without scrolling
- the dashboard says when it does not know
- every number leads to the trade or rule behind it

```sh:surface
mt trade --strategies KEY,…
mt report --strategy KEY --symbols SYM,… --start DATE --end DATE
mt env list --service {web|bot}
```

# entities

| name | idea |
| --- | --- |
| asset | an instrument identified the same way across providers and ownership |
| bar | one open, high, low, close and volume over one span |
| feed | the source that supplies bars to a run |
| session | one exchange trading day from open to close |
| universe | the assets that pass price and turnover selection |
| signal | the condition that makes a strategy act |
| candidate | a proposed entry with price, stop and direction |
| order | one instruction sent to the broker |
| fill | the part of an order the broker completed |
| position | the exposure the broker reports |
| holding | the exposure a strategy manages, with stop and staged exits |
| ladder | the staged exits that reduce a holding |
| trade | one round trip from flat to flat |
| equity | the account value at one moment |
| snapshot | the realtime account, positions and open orders |
| ledger | trades, fills and profit over a period |
| levels | the marks a chart draws for entry and averages |
| state | the record the bot publishes for the dashboard |
| event | one dated note inside the published state |
| heartbeat | the time of the last publication |
| login | an authenticated web visitor |
| rules | the trading settings the bot and the web share |
| strategy | one named way to enter and manage holdings |
| family | strategies that share entry logic |
| variation | one configured member of a family |
| benchmark | the symbol every comparison uses |
| report | one backtest run and its artifacts |

# config

- the bot and the web share validated rules
- service settings own credentials, hosts and runtime limits
- unknown nested fields fail validation
- published rules omit secrets
- every layer reads config
- deployment sends each service only the keys it needs

```sh:types
{SECTION}__{FIELD}          # one section per concern
{SECTION}__TIMEOUT__{FIELD} # connect, read, write and pool seconds
{PREFIX}LOOKBACK_DAYS       # a window of calendar days
{PREFIX}LOOKBACK_SESSIONS   # a window of exchange sessions
```

# data

- vendor[broker] supplies account, positions, orders, fills, quotes and clock
- broker metadata owns trading permissions
- vendor[calendar] supplies common stocks and scheduled earnings
- an earnings event date differs from its announcement date
- asset identity is immutable across providers and ownership
- crypto identity includes base and quote
- option identity includes underlying, expiration, strike and right

```py:surface
bars(assets, timeframe, start, end?) → {asset: [bar]}
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

A run reads bars through one feed. Historical observations end at the engine clock.

# bot

## portfolio

- portfolio owns the universe, sizing, exposure, ownership and execution
- strategies reach observations and actions only through portfolio
- one risk budget divides into every per-trade limit
- a strategy holds at most half the book

```py:surface
universe
    active, tradable, fractionable stocks ∩ calendar common stocks
    price > universe.price_usd_min; turnover > universe.turnover_usd_min
    rank by turnover descending, symbol ascending

sizing(equity, price, stop_distance, direction)
    per_trade = risk.per_day_max / risk.positions_max
    allocation = 1 / risk.positions_max
    quantity = min(equity * allocation / price, equity * per_trade / stop_distance)
    short → whole shares; otherwise risk.quantity_decimal_places
    quantity * price < risk.notional_usd_min → 0

enter(strategy, candidate, session)
    non-stock, paused strategy, held asset or quote through stop → skip
    short without broker shortable permission → skip
    positions including pending ≥ risk.positions_max → skip
    gross exposure including pending and the new entry ≤ equity

protect(holding)
    resting stop through last price → exit at market

iteration
    reconcile positions; check the daily loss; manage holdings; run strategies
    equity ≤ session open value * (1 - risk.per_day_max) →
        cancel orders; exit all; block entries for the day
        retry liquidation on later iterations
```

```
Σ risk(open holdings) ≤ risk.per_day_max * equity
count(holdings per strategy) ≤ risk.positions_max / 2
holding.stop never widens
```

## strategy → [strategies]

- a strategy owns its signals and its holding management
- strategies reach observations and actions only through portfolio

## execution

- vendor[engine] supplies lifecycle callbacks, order submission and fills
- paper and live both run through vendor[broker]
- a report simulates execution under the same portfolio and strategy contracts
- a report starts with an empty account funded by backtest.budget_usd
- asset defaults are simulation assumptions, not historical eligibility
- empty or non-stock assets fail before any artifact is written
- a report returns statistics, trades and plots against the benchmark

Breakout reports include warm-up. A daily report uses engine daily bars; it does
not establish minute-level fill fidelity.

# state

- state carries status, selected and paused strategies, heartbeat, rules and
  bounded events
- status ∈ starting | running | stopped | failed
- unknown fields fail validation
- one bot writer replaces validated JSON at `mt:state` every export interval
- state has no expiry
- a vendor[store] publication failure warns and trading continues
- shutdown publication is best effort with a bounded wait

A read returns absent or validated state. Read failures stay errors. The web
keeps the last state across its own restarts and across a stale heartbeat.

```protocol
bot             store           web
│               │               │
├──state───────→│               │
│               │←──read────────┤
│               ├──state───────→│
│               │               │
```

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

```http:surface
GET /api/strategies
# reported rules, otherwise configured rules
# selection: online | paused | unselected | unknown

GET /api/ledger
# orders, fills, profit and bot state
# gross loss is a positive magnitude
# stale when state is absent or the heartbeat is overdue

GET /api/snapshot
# realtime account, positions and open orders

GET /api/bars?symbol={symbol}&timeframe={timeframe}&opened={date}&closed={date}
# configured timeframes; symbol → asset
# stock hours follow exchange sessions; crypto and options use native hours

GET /api/levels?symbol={symbol}&strategy_key={key}&side={side}&entry={price}&opened={date}
# entry marks and averages; non-stock → no equity strategy levels
```

Snapshot and ledger share one account observation. Every response carries the
read_at of its source. An older response never replaces a newer account value.

## trades

- a trade spans flat to flat
- partial exits accumulate into their trade
- a reversal starts a new trade
- missing entry history → the entry time is unavailable
- calendar periods use exchange time: monday-to-date and month-to-date
- strategy totals, benchmark comparisons and equity selection share boundaries

```
baseline = the last observation before the boundary
baseline = the first observation when funding began inside the period
baseline ∈ {0, absent} → percentage unavailable
```

# refs

[strategies]: spec.strategies.md
