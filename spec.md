---
name: money-tree
vendors:
  broker: alpaca
  engine: lumibot
  host: railway
---

- the bot runs the selected strategies against one broker account
- the mode selects paper or live trading and supplies every service variable
- a report replays one strategy over a date range and writes one run directory
- the dashboard shows the account, orders, fills, and the bot heartbeat to allowed users
- a paused strategy opens no position and runs its open positions to their exits

```sh
src/
    bot/
        strategies/
            base.py
            daily_base.py
            orb_base.py
            shared.py
            tfb_50.py
        backtest.py
        broker.py
        config.py
        export.py
        order_tag.py
        portfolio.py
        report.py
        trade.py
        types.py
    cli/
        __main__.py
    ui/
        assets/
            dashboard.css
            dashboard.html
            dashboard.js
            favicon.svg
            theme.js
        alpaca.py
        app.py
        auth.py
        config.py
        dashboard.py
        ledger.py
        strategies.py
```

```sketch
┌───────┐  signed snapshot, 5s  ┌───────┐  cookie session  ┌─────────┐
│  bot  │ ────────────────────→ │  web  │ ←─────────────── │ browser │
└───┬───┘                       └───┬───┘                  └─────────┘
    │ orders, bars                  │ account, orders, fills, bars
    ↓                               ↓
vendor[broker]                  vendor[broker]
```

- `mise.{mode}.toml` declares every variable a service reads
- a variable declared empty is a secret and lives in `.env.{mode}`
- neither mode inherits a value from the other

# strategies

```text:types
ET ≔ US Eastern Time
account ≔ account value when the position opens
R ≔ |entry price − initial stop|
range(p) ≔ opening range low + p · opening range size
SMA(n), ATR(n), RSI(n), ADX ≔ standard indicators over n candles; n = 14 unless stated
whole shares ≔ each leg rounds down to a whole share; a slice under one share is skipped
rescan ≔ the candidates of the day are offered again on every iteration to the close
```

- market ≔ US stocks, market cap ≥ $500M, share price ≥ $5, average daily turnover ≥ $20M
- sorting ≔ last completed session close · volume, highest first, when candidates exceed room
- position size ≔ 10% of account; short legs are whole shares
- a stop at or beyond the last price closes the position at market

## breakout

| | ORB (5-minute) | ORB (10-minute) |
|---|---|---|
| state | enabled | paused |
| candle | 5 min | 10 min |
| opening range | 09:30–09:35 ET | 09:30–09:40 ET |
| cumulative volume ≥ n · 20-day average at the same time | n = 1.3 | n = 1.5 |
| entry window | 09:35–10:30 ET | 09:40–10:30 ET |
| max entry beyond the range | none | 0.25 · range size |
| risk per trade | 0.15% of account | not set |
| min risk:reward | not set | 1:2 |
| breakeven and trail at | +1.5R | +2R |
| close 50% / 25% / 25% at | +1.5R / +2.5R / +4R | +2R / +3R / +5R |

```text:surface
setup
    marks ≔ range high, midpoint, low
    range size ≥ 0.4% of price
    initial stop distance ∈ [1%, 5%] of price
    volume is read at the signal candle close

entry
    long signal ≔ first close above range high · short signal ≔ first close below range low
    signal candle ∈ last 2 completed candles
    order ≔ open of the next candle
    entry block ≔ live quote already through the initial stop
    breakout positions ≤ 3 across both variants

risk
    long stop ≔ range(0.75) · short stop ≔ range(0.25)
    trail ≔ 1.5 · ATR(14) on strategy candles across sessions; needs 15 completed candles
    the active stop never moves past breakeven into a loss

exit
    close any remainder before 15:55 ET
```

## daily

| | Momentum (SMA) | TFB-50 |
|---|---|---|
| state | enabled | enabled |
| turnover window | daily | last 20 sessions |
| price | price > SMA(50) > SMA(200) | price > SMA(50) > SMA(50) 3 sessions ago |
| momentum | RSI ≥ 50 and ADX ≥ 25 | ADX ≥ 20 |
| signal | day 1 close < SMA(20); day 2 close > SMA(20) and > day 1 close | close > previous candle high |
| order | day 3 open | next open |
| earnings | no entry within 5 days before; exit the day before | none |
| positions | portfolio cap | ≤ 5 |
| risk per trade | not set | 0.5% of account |
| stop | highest close since entry − 1.5 · ATR | entry − 2 · ATR, then highest close since entry − 2 · ATR |

```text:surface
market state ≔ SPX > SMA(20) · direction ≔ long

entry
    window ≔ market open to close, rescan
    order ≔ the signal open, or the first later iteration with a free slot and free money
    one entry per symbol per session

risk
    the stop recalculates daily and only moves up
    a daily close below the stop exits at the next open

exit
    signal exit ≔ daily close < SMA(20) or RSI(14) < 50
    shared rules ≔ stop loss, emergency exit
```

## portfolio

```text:surface
positions ≤ 10 across strategies · an entry is skipped when gross exposure ≥ equity
position fraction ≤ min(POSITION_FRACTION_MAX, 10%)
risk per trade ≤ RISK_PER_TRADE_MAX unless the strategy sets its own

emergency exit
    equity ≤ session baseline · (1 − RISK_PER_DAY_MAX) → cancel open orders, exit every holding, lock the day
```

# bot

```text:private
trade(strategies)
    exporter ≔ signed snapshot publisher for STATE_EXPORT_URL with STATE_EXPORT_SECRET
    publish starting → run vendor[engine] → publish running
    SIGTERM → stop all → publish stopped · failure → publish failed

cron:export[5s]()
    POST {run_id, sequence, status, strategies, paused, started_at, heartbeat_at, configuration, events ≤ 50}

backtest(strategy, start, end, symbols?)
    breakout → vendor[broker] minute bars, 60 warm-up days · daily → Yahoo daily bars
    budget ≔ $100k · benchmark ≔ SPY
```

- vendor[engine] is [lumibot][engine]

# report

```sh
runs/{strategy}-{start}-{end}/
    stats.csv
    trades.csv
    settings.json
    backtest.log
    plot.html
    indicators.html
    tearsheet.html
    tearsheet_metrics.json
```

# web

```text:surface
GET  /healthz              public
GET  /login                public · vendor[host] oauth
GET  /auth/callback        public · email ∉ ALLOWED_RAILWAY_EMAILS → 403
POST /internal/state       public · signature ≤ 30s old, body ≤ 64 KiB, else 401 · 413 · 422
POST /logout               clears the session and site data
GET  /                     dashboard
GET  /assets/{file}        immutable
GET  /api/session          csrf token
GET  /api/strategies
GET  /api/bars             symbol, timeframe ∈ {5Min, 1Hour, 1Day}, opened, closed
GET  /api/levels
GET  /api/ledger
GET  /api/pulse
```

| response | server cache | browser max-age | browser poll |
|---|---:|---:|---:|
| pulse: account, positions, open orders | 2 s | 0 | 2 s |
| ledger: orders, fills, P&L, bot state | 60 s | 10 s | 30 s |
| strategies | — | 60 s | 30 s |
| bars · levels | 120 s, 64 keys | 60 s · 300 s | on demand |

- every route outside the public paths needs a session cookie
- an unsafe method also needs the `X-CSRF-Token` header
- the bot is stale when no heartbeat arrives within 15 s
- a vendor[broker] 429 becomes 503 with Retry-After; any other upstream error becomes 502

# deploy

```text:surface
vendor[host] project money-tree — managed in the Railway dashboard
    money-tree-web  uvicorn ui.app:create_app · healthcheck /healthz · watches src/ui, export.py, types.py
    money-tree-bot  mt trade --strategies $STRATEGIES · private endpoint money-tree · watches src/bot, src/cli

deploy()
    push to main → vendor[host] builds the watched paths → rolls the service
```

- each service holds its own variables in the dashboard; secrets are sealed there

---

# refs

[engine]: https://github.com/Lumiwealth/lumibot#quick-start
