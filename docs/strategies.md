# Money Tree — strategies and rules

A record of every trading strategy, risk rule and execution rule in the Money Tree bot as of 2 Oct 2026 (commit `1367b2c`). All values come from `mise.toml`, `spec.md`, `spec.strategies.md` and the code under `src/mt/`.

## Contents

1. [System overview](#1-system-overview)
2. [Shared risk rules](#2-shared-risk-rules)
3. [Universe selection](#3-universe-selection)
4. [Market data](#4-market-data)
5. [Indicators](#5-indicators)
6. [Portfolio loop and execution](#6-portfolio-loop-and-execution)
7. [Breakout family](#7-breakout-family-breakout_5m-breakout_10m-breakout_15m)
8. [Daily family](#8-daily-family-daily_sma-daily_tfb-daily_20sma)
9. [Order codes and reasons](#9-order-codes-and-reasons)
10. [Trade accounting](#10-trade-accounting)
11. [Backtesting](#11-backtesting)
12. [Removed strategies](#12-removed-strategies)
13. [Lessons from the 27 Sep 2026 trade audit](#13-lessons-from-the-27-sep-2026-trade-audit)
14. [Full configuration reference](#14-full-configuration-reference)

---

## 1. System overview

- The bot trades selected US-equity strategies on one Alpaca account (`BROKER__MODE = paper`).
- One process (`mt trade --strategies KEY,…`) runs every strategy through one `Portfolio`, built on Lumibot.
- Strategies reach bars, quotes and orders only through the portfolio.
- One daily loss limit stops every strategy for the day.
- One risk budget sizes every entry.
- Benchmark symbol: `SPY`.
- Configured strategy list: `breakout_5m, daily_sma, daily_tfb, breakout_10m, daily_20sma, breakout_15m`.

### Strategy register

| key | name | family | code | stop handling | paused (current config) | holdings cap |
|---|---|---|---|---|---|---|
| `breakout_5m` | Breakout 5m | Intraday breakout | `o` | resting stop order at the broker | no | 10 |
| `breakout_10m` | Breakout 10m | Intraday breakout | `m` | resting stop order at the broker | no | 10 |
| `breakout_15m` | Breakout 15m | Intraday breakout | `f` | resting stop order at the broker | no | 10 |
| `daily_sma` | Daily SMA | Daily trend | `s` | portfolio watches the stop | **yes** | 6 |
| `daily_tfb` | Daily TFB | Daily trend | `t` | portfolio watches the stop | **yes** | 6 |
| `daily_20sma` | Daily 20SMA | Daily trend | `w` | portfolio watches the stop | no | 6 |

- The key splits into family (first segment) and variation (the rest).
- A cap counts holdings of that variation alone, pending entries included.
- Breakout caps default to `RISK__POSITIONS_MAX // 2` = 10. Daily caps come from `*_HOLDINGS_MAX` = 6.
- A paused strategy places no new entries. It still manages and exits what it holds.

---

## 2. Shared risk rules

| rule | value |
|---|---|
| daily loss limit (`RISK__PER_DAY_MAX`) | 2% of the session-open equity |
| max open positions, whole account (`RISK__POSITIONS_MAX`) | 20 |
| risk per trade | `per_day_max / positions_max` = 0.1% of equity |
| max allocation per trade | `1 / positions_max` = 5% of equity |
| max notional per entry (`RISK__NOTIONAL_USD_MAX`) | $100 |
| min notional per entry (`RISK__NOTIONAL_USD_MIN`) | $1 |
| quantity precision (longs) | 9 decimal places (fractional shares) |
| quantity precision (shorts) | whole shares |

### Sizing formula (`src/mt/sizing.py`)

```
per_trade  = 0.02 / 20 = 0.001
allocation = 1 / 20    = 0.05
quantity   = min( equity * allocation / price,
                  equity * per_trade  / stop_distance,
                  100 / price )
long  → round down to 9 decimals
short → round down to whole shares
quantity * price < $1 → no trade (0)
```

- In practice the $100 cap binds on almost every entry in a $100k account.
- A short on a stock priced above $100 rounds to 0 shares and is skipped.

### Invariants

- Σ risk of open holdings ≤ 2% of equity.
- Entry notional ≤ $100.
- Holdings per variation ≤ `positions_max / 2`.
- A stop never widens. Long stops only rise; short stops only fall (`next_stop`).
- Closing orders never exceed the broker position.
- Stops round to cents: long stops round down, short stops round up.

### Daily loss limit

- The first iteration of each session records the equity as the session baseline.
- Every iteration checks `equity ≤ baseline × (1 − 0.02)`.
- On a breach: cancel all orders, exit every position at market (`mt-liquidate-…` orders), block entries for the rest of the day.
- Later iterations retry the liquidation.

### Entry guards (`Portfolio.enter`)

An entry is skipped when any of these hold:

- the asset is not a stock
- the strategy is not selected or is paused
- the asset is already held or has a pending entry (any strategy)
- the stop is not beyond the entry price (`direction × (price − stop) ≤ 0`)
- a short on a security the broker marks not shortable
- owned positions + pending entries ≥ 20
- sizing returns 0, or gross exposure + pending notional + this entry > equity
- one entry per asset per strategy per session (`_traded` set, cleared each session)

---

## 3. Universe selection

Rebuilt once per session, before the open.

1. Alpaca assets that are active, tradable and fractionable, of class `us_equity`.
2. Intersect with Finnhub common stocks.
3. Last completed daily close > $5 (`UNIVERSE__PRICE_USD_MIN`).
4. Mean daily turnover (close × volume) over the last 20 sessions > $20M (`UNIVERSE__TURNOVER_USD_MIN`, `UNIVERSE__TURNOVER_SESSIONS`).
5. Look back 45 calendar days for the price and turnover tests (`UNIVERSE__LOOKBACK_DAYS`).
6. Rank by turnover descending, then symbol ascending.

Strategies rank their own candidates by the latest single-session turnover (volume × close), highest first.

---

## 4. Market data

| item | source |
|---|---|
| daily bars | Alpaca SIP feed, `adjustment = all`, end ≤ wall clock − 15 min |
| intraday bars | Alpaca IEX feed, `adjustment = all` |
| quote | latest IEX **trade** price; older than 120 s → absent; absent → the decision waits |
| daily lookback | 410 calendar days (`PORTFOLIO__LOOKBACK_DAYS`) |
| earnings dates | Finnhub calendar |
| market cap | Finnhub company profile (cached per symbol per session) |
| exchange calendar | `exchange_calendars` XNYS, America/New_York |

- Only completed bars are used. Daily frames drop today's bar. Intraday frames drop the bar still forming.
- Missing series → empty list. Unsupported asset type → error before the request.

---

## 5. Indicators

All indicator periods use `INDICATORS__PERIOD_BARS = 14`. Library: `pandas_ta_classic`.

| indicator | definition |
|---|---|
| `SMA_n` | rolling mean of close over n bars |
| `RSI_14` | Wilder RSI on close |
| `ATRr_14` | ATR (RMA) on high, low, close |
| `ADX_14` | ADX on high, low, close |
| turnover | close × volume |

Daily frames carry `SMA_20` plus each selected daily strategy's trend lengths (50, 200).

---

## 6. Portfolio loop and execution

- Iteration interval: 1 minute (`PORTFOLIO__ITERATION_MINUTES`).
- Preparation starts 30 minutes before the open (`PORTFOLIO__OPENING_LEAD_MINUTES`).
- Non-session days skip every iteration.

### Each iteration, in order

1. **Begin day** (first iteration of a session): record the baseline equity, clear events, clear the one-entry-per-session sets, call each strategy's `begin`, log paused strategies.
2. **Reconcile** with the broker:
   - drop holdings with no broker position
   - drop pending entries older than 5 minutes with no active order
   - cancel open orders with no position, holding or pending entry
   - exit at market any position with no holding, pending entry or closing order ("stray")
   - re-place resting stops whose quantity no longer covers the position (drift > 0.000001 shares)
3. **Daily loss check** (section 2). A locked day stops here.
4. **Prepare** (once per session): broker asset permissions, universe, daily bars and indicators.
5. **Manage holdings**: for each holding without a pending or closing order:
   - a watched (non-resting) stop with the quote through it → exit at market
   - otherwise call the strategy's `manage`
6. **Run strategies**: each selected, unpaused strategy whose entry window contains `now` runs its scan.

### Orders

- All orders are `day` orders.
- Entries and exits are market orders.
- Resting stops are stop orders for the full held quantity.
- A resting stop that the quote has already passed → exit at market instead.
- Each fill re-averages the entry price and rebuilds the ladder from the filled quantity.
- A watched stop re-anchors to `fill price − direction × initial stop distance` after each fill (never widening).

---

## 7. Breakout family (`breakout_5m`, `breakout_10m`, `breakout_15m`)

An opening-range breakout with a volume test. Long and short. Exits by the close.

### Family settings (shared)

| setting | value | meaning |
|---|---|---|
| `range_fraction_min` | 0.4% | min range width / price |
| `long_stop_fraction` | 0.75 | long stop = low + 0.75 × width |
| `mid_fraction` | 0.5 | range midline (drawn on the chart) |
| `short_stop_fraction` | 0.25 | short stop = low + 0.25 × width |
| `stop_fraction_min` | 1% | min stop distance / price |
| `stop_fraction_max` | 5% | max stop distance / price |
| `target_fractions` | 50%, 25% | share closed at target 1 and target 2 |
| `lookback_sessions` | 20 | sessions in the volume average |
| `signal_bars_max` | 2 | max age of the breakout bar, in bars |
| `trail_atr_multiple` | 1.5 | trail distance in ATRs |
| `trail_bars_min` | 15 | bars after breakeven before the trail starts |
| `scan_minutes` | 60 | the entry window ends this long after the open |
| `close_lead_minutes` | 6 | flatten this long before the close (15:54 ET) |
| `confirm_lookback_days` | 45 | calendar days of intraday bars for the volume test |
| `trail_lookback_days` | 5 | calendar days of intraday bars for the trail ATR |

### Variation settings

| setting | 5m | 10m | 15m |
|---|---|---|---|
| `opening_minutes` (range length and bar size) | 5 | 10 | 15 |
| `volume_multiple` | 1.3× | 1.5× | 1.7× |
| `target_multiples` (of initial stop distance, R) | 1.5, 2.5, 4.0 | 2.0, 3.0, 5.0 | 1.5, 2.5, 4.0 |
| `entry_extension_max` (× range width) | none | 0.25 | 0.20 |
| entry window (ET, regular day) | 09:35 – 10:30 | 09:40 – 10:30 | 09:45 – 10:30 |

### Entry

1. Runs only on iterations where `minute % opening_minutes == 0` (once per new bar).
2. Skip when the variation is at its cap.
3. Bars are of size `opening_minutes` (5Min, 10Min, 15Min).
4. Opening range = max high and min low of bars in `[open, open + opening_minutes)`.
5. Signal = the first bar after the range whose close is above the high (long) or below the low (short).
6. Once a break is found, the asset is marked scanned for the session and is not re-tested.
7. Setup checks at the signal close:
   - range width ≥ 0.4% of the close
   - stop distance `|close − stop| / close` within 1%–5%
8. The signal bar must be at most 2 bars old.
9. Rank signals by latest daily turnover, highest first.
10. Volume test: cumulative regular-session volume from the open to the signal bar's clock time, divided by the mean of the same cumulative volume over the previous 20 sessions, must be ≥ `volume_multiple`. Fewer than 20 sessions of history → fail.
11. Read the quote. No quote → skip for now.
12. Extension test (10m, 15m): long skips when `price > high + max × width`; short skips when `price < low − max × width`.
13. Stop = `low + 0.75 × width` (long) or `low + 0.25 × width` (short).
14. Submit a market entry. After the fill, place a resting stop at the broker.

### Management

- Targets = `entry + direction × R × multiple`, where R = initial stop distance.
- Target 1: close 50% of the original quantity. Move the stop to entry (breakeven). Record the breakeven time.
- Target 2: close 25% of the original quantity.
- Target 3: close the rest.
- Partial short exits round down to whole shares. Zero shares → no order.
- After target 1, once 15 regular-session bars have closed since breakeven, trail the stop to `highest − 1.5 × ATR(14)` (long) or `lowest + 1.5 × ATR(14)` (short), ATR on the variation's bar size.
- The stop never widens.
- At 6 minutes before the close, exit the rest at market (reason `close`).
- After each management pass, refresh the resting stop at the broker.

### Worked example (breakout_5m, long)

- Range 09:30–09:35: high 101.00, low 100.00, width 1.00 (1%).
- 09:40 bar closes at 101.20 → long signal.
- Stop = 100.00 + 0.75 × 1.00 = 100.75. Distance 0.45 / 101.20 = 0.44% → **fails** the 1% floor → no trade.
- With a range of 98.00–101.00 (width 3.00): stop = 100.25; distance 0.95 / 101.20 = 0.94% → still fails. Range 97.00–101.00: stop 100.00, distance 1.19% → passes.
- Entry 101.20, R = 1.20: targets 103.00, 104.20, 106.00.

---

## 8. Daily family (`daily_sma`, `daily_tfb`, `daily_20sma`)

Daily trend-following entries. Long only. Positions held across sessions.

### Family settings (shared)

| setting | value | meaning |
|---|---|---|
| `DAILY__AVERAGE_SESSIONS` | 20 | the short average (SMA 20) |
| `DAILY__EXIT_RSI_MAX` | 50 | RSI below this → exit |
| `EARNINGS__BLOCK_DAYS` | 5 | calendar days ahead scanned for earnings |

### Shared entry rules

- Market filter: SPY's last daily close must be above SPY's SMA 20. Otherwise no entries that session.
- Earnings filter: skip a stock with a scheduled earnings date within the next 5 calendar days.
- Scan once per session on the last completed daily bar. Cache the candidate list for the session.
- Rank candidates by latest daily turnover, highest first.
- One entry per asset per session.
- Enter at the next open, else the next iteration inside the window with a fresh quote.
- The candidate is re-priced at the live quote. ATR variations keep the same stop distance.

### Shared exit rules

- Earnings: exit at market from the session before the earnings date through the earnings date (during regular hours).
- An unsubmitted earnings exit retries on the next iteration.
- Stop: the portfolio checks the quote each minute; quote at or through the stop → exit at market.

### 8.1 `daily_sma` — SMA trend with a 20-day cross (paused)

Settings: `trend_sessions = 50`, `trend_sessions_long = 200`, `rsi_min = 50`, `adx_min = 25`, `stop_atr_multiple = 1.5`, `holdings_max = 6`.

Entry signal (all on the last completed daily bar):

```
close > SMA50 > SMA200
RSI14 ≥ 50
ADX14 ≥ 25
close crosses above SMA20: close > SMA20 and close[-1] < SMA20[-1]
close > close[-1]
```

- Entry window: open to close.
- Initial stop = entry − 1.5 × ATR14 (daily).

Management (each iteration):

- Trail: stop = max(stop, highest close since entry − 1.5 × ATR14).
- Exit (reason `signal`) when the last daily close < SMA20 or RSI14 < 50.

### 8.2 `daily_tfb` — trend-following breakout (paused)

Settings: `trend_sessions = 50`, `turnover_sessions = 20`, `adx_min = 20`, `trend_lag_sessions = 3`, `stop_atr_multiple = 2.0`, `holdings_max = 6`.

Entry signal:

```
mean turnover over 20 sessions > $20M
close > SMA50
SMA50 > SMA50 three sessions ago (rising)
ADX14 ≥ 20
close > previous high
```

- Entry window: open to close.
- Initial stop = entry − 2.0 × ATR14 (daily).
- Management: same as `daily_sma` with a 2.0 × ATR trail, and the same SMA20 / RSI exit.

### 8.3 `daily_20sma` — 20-day cross with staged targets (active)

Settings:

| setting | value |
|---|---|
| `trend_sessions` / `trend_sessions_long` | 50 / 200 |
| `rsi_min` / `rsi_max` | 50 / 70 |
| `adx_min` | 25 |
| `market_cap_usd_min` | $2B |
| `entry_minutes` | 5 |
| `stop_fraction` | 5% |
| `breakeven_gain` | 10% |
| `target_gains` | +15%, +25% |
| `target_fractions` | 50%, 25% |
| `trail_atr_multiple` | 1.5 |
| `trail_hours` | 4 (240-minute bars) |
| `trail_lookback_days` | 30 |
| `holdings_max` | 6 |

Entry signal:

```
close > SMA50 > SMA200
50 ≤ RSI14 ≤ 70
ADX14 ≥ 25
close crosses above SMA20
market cap ≥ $2B (Finnhub; unreadable → skip)
```

- Entry window: the first 5 minutes of the session (09:30–09:35 ET).
- Initial stop = entry × 0.95.

Management (each iteration, with a fresh quote):

1. Mark the highest price seen.
2. Ladder: at entry × 1.15 close 50% of the original quantity; at entry × 1.25 close 25%. The remaining 25% trails.
3. While the highest price < entry × 1.10, the stop stays at entry × 0.95.
4. Once the highest ≥ entry × 1.10: stop = max(stop, entry, highest − 1.5 × ATR14 on 4-hour bars over 30 days).
5. Inside the first 5 minutes of a session: last daily close < SMA20 or RSI14 < 50 → exit the rest (reason `signal`).

---

## 9. Order codes and reasons

Every order carries a `client_order_id`:

```
mt-{code}-{reason}-{16 hex chars}     strategy order
mt-liquidate-{16 hex chars}           daily-loss liquidation
```

| code | strategy |
|---|---|
| `o` | breakout_5m |
| `m` | breakout_10m |
| `f` | breakout_15m |
| `s` | daily_sma |
| `t` | daily_tfb |
| `w` | daily_20sma |

| reason | meaning |
|---|---|
| `entry` | opening order |
| `stop` | initial stop |
| `breakeven` | stop moved to entry |
| `trail` | trailing stop |
| `target_1`, `target_2`, `target_3` | ladder stages |
| `close` | end-of-day flatten (breakout) |
| `signal` | daily exit signal |
| `earnings` | pre-earnings exit |
| `limit` | daily loss liquidation |

- Codes are frozen. The dashboard attributes orders and trades through them.
- An order without an `mt-` code is "unattributed".
- A stop-type order without a parseable reason reads as `stop`.

---

## 10. Trade accounting

- A trade is one round trip from flat to flat.
- Partial exits add to their trade.
- A reversal (a fill that crosses through zero) closes the trade and starts a new one with the excess.
- The trade's strategy is the code of its first attributable entry fill.
- Missing entry history → the entry time is unavailable.
- Positions at or below 0.000000001 shares count as flat.
- Periods: Monday-to-date (`W`) and month-to-date (`M`).
- Baseline = the last daily equity before the period, else the first equity inside it. Baseline 0 or absent → percentage unavailable.
- Strategy totals, benchmark comparison and equity selection share one period.
- Totals: trade count, wins (P&L > 0), net P&L, gross profit, gross loss (a positive magnitude; zero-P&L trades count as losses).

---

## 11. Backtesting

```
mt report --strategy KEY --symbols SYM,… --start DATE --end DATE
→ runs/{key}-{start}-{end}/  stats.csv, trades.csv, settings.json, backtest.log, plot.html, indicators.html
```

- Same portfolio, strategy and trade code as live.
- Starting cash $100,000 (`BACKTEST__BUDGET_USD`). Benchmark SPY.
- Breakout → Alpaca minute bars with 60 trading days of warm-up.
- Daily → Yahoo daily bars through Lumibot. Daily fills are approximate.
- Simulated assets default to: us_equity, active, tradable, marginable, shortable, easy to borrow, fractionable.
- Empty or non-stock symbol lists fail before any artifact is written.

---

## 12. Removed strategies

Removed on 28 Sep 2026 (commit `822746d`). All three were paused when removed. Specs and settings are kept here for reference.

### 12.1 `intraday_mim` — intraday momentum

Source: Gao, Han, Li & Zhou (2018); noise band after Zarattini, Aziz & Barbon (2024). Resting stop.

```
signal
    move = SPY first 30-minute bar close / prior session close − 1
    band = mean |move| over the prior 14 sessions
    |move| < 1.0 × band → skip the session
entry
    window = close − 30 min → close − 6 min
    move > 0 → buy SPY; move < 0 → buy SH
    stop = entry × (1 − 1.0 × band)
management
    6 minutes before the close → close the rest
```

Settings: long `SPY`, short `SH`, first 30 min, noise 14 sessions, lookback 30 days, holdings max 1.

### 12.2 `allocation_baa` — Bold Asset Allocation

Source: Keller (2022). Monthly. Portfolio-watched stop.

```
momentum
    fast = (12·r1 + 4·r3 + 2·r6 + r12) / 4
    slow = p0 / mean(p0 … p12) − 1
selection, once per month (closes = last daily close of each month)
    canaries with fast < 0 ≥ breadth (1) → defensive, else offensive
    offensive → top 1 offensive symbol by slow
    defensive → top 3 defensive symbols by slow; slow below cash → cash symbol
    missing canary or cash closes → skip the month until readable
entry
    window = open + 15 min → close
    every pick not held → enter; stop = entry × 0.75
management
    price ≤ stop → exit
    inside the window, a holding outside the picks → exit
```

Symbols: canary `SPY, EFA, EEM, AGG`; offensive `QQQ, EEM, EFA, AGG`; defensive `TIP, DBC, BIL, IEF, TLT, LQD, BND`; cash `BIL`. Holdings max 3.

### 12.3 `quality_gp` — gross profitability

Source: Novy-Marx (2013). Monthly. Portfolio-watched stop. Fundamentals from SEC EDGAR.

```
ranking, once per month
    universe = the first 1000 universe stocks
    score = gross profit / total assets, latest annual filing
    gross profit = GrossProfit, else revenue − cost of revenue
    filing older than 460 days → skip
    industry ∈ {Banking, Financial Services, Insurance, Real Estate} → skip
    keep the top 20
    unreadable filings or industries → retry after 30 minutes
entry
    window = open + 15 min → close
    the top 6 not held → enter; stop = entry × 0.75
management
    price ≤ stop → exit
    inside the window, a holding outside the top 20 → exit
```

---

## 13. Lessons from the 27 Sep 2026 trade audit

Source: `Money-Tree-Trade-Audit.pdf` (paper account, sessions 22–25 Sep 2026, 855 orders, 1,381 fills).

### Confirmed correct

- Opening ranges, levels and resting stops matched a replay to the cent on all 15 breakout entries.
- Timeframes, entry windows and volume confirmation matched the rules.
- All 25 daily entries passed the coded setup.
- Stops never widened.
- Pending orders counted toward caps.
- No two strategies ever held the same symbol.
- Shorts used whole shares; partial short exits rounded down.

### Errors found

| id | problem | effect |
|---|---|---|
| E1 | Prices came from the IEX quote **midpoint** (Lumibot `get_last_price`); wide IEX spreads made targets look hit | 36 of 46 breakout partial exits (14–25 Sep) fired before the real price reached target 1 |
| E2 | Each phantom target moved the stop to entry, and the real price was already below it | the rest sold at market within minutes, near breakeven |
| E3 | Stops placed from Lumibot's cached position size after a position closed | opened new unmanaged positions (MARA, SAM, SUNB) |
| E4 | Stray positions counted toward the 20-position limit | breakout_5m placed zero orders for three sessions |
| E5 | 13 of 17 daily holdings sold before the open on 25 Sep with no coded reason | coincided with a deploy; holdings live only in memory |
| E6 | One breakout_10m entry passed its extension limit | config value at runtime unverified |

### Issues found

- Entries went out 4–28 minutes after the scan that found the signal, so fills landed far past the breakout level.
- Stop-band and extension checks ran on the signal close, not the fill price.
- Sizing and guards used the same midpoint, so some fills exceeded the $100 cap.
- Heavy stop-order churn: 376 stop orders, 328 cancelled, mostly during partial fills.
- Volume confirmation read IEX volume only, a small share of consolidated volume.

### Recommended changes (from the audit)

| # | change | status at `1367b2c` |
|---|---|---|
| P1 | Use the latest trade price, not the quote midpoint; reject wide spreads | latest IEX trade price, max age 120 s (spread check not present) |
| P2 | Rest target orders at the broker (limit or bracket/OCO) | not done |
| P3 | Read broker positions before placing a stop; cancel all stops once flat | `_held` reads refreshed broker positions |
| P4 | Flag and close or adopt positions no holding owns | strays exit at market each iteration |
| P5 | Re-check stop band and extension at the entry price before submitting | extension uses the live quote; stop band still uses the signal close |
| P6 | Prefetch the universe and confirmation bars before 09:35 | universe prepared before the open; confirmation bars fetched at scan time |
| P7 | Log each exit's reason and inputs | reasons are encoded in order codes |
| P8 | Deploy only while flat, or rebuild holdings from broker positions and order codes on start | not done; holdings are in memory only |

### Realized P&L in the audit window

- breakout_5m (25 Sep): +$2.34 over 13 trades
- breakout_10m (25 Sep): +$3.77 over 2 trades
- daily_sma (22–25 Sep): −$373.16
- daily_tfb (22–25 Sep): +$174.61

---

## 14. Full configuration reference

Trading-relevant values from `mise.toml`.

```toml
STRATEGIES = "breakout_5m,daily_sma,daily_tfb,breakout_10m,daily_20sma,breakout_15m"
BENCHMARK_SYMBOL = "SPY"

## broker
BROKER__MODE = "paper"

## bars
BARS__SYMBOLS_PER_REQUEST = "200"
BARS__INTRADAY_FEED = "iex"
BARS__DAILY_FEED = "sip"
BARS__SIP_DELAY_MINUTES = "15"
BARS__TRADE_MAX_AGE_SECONDS = "120"

## risk
RISK__PER_DAY_MAX = "0.02"
RISK__POSITIONS_MAX = "20"
RISK__NOTIONAL_USD_MIN = "1.0"
RISK__NOTIONAL_USD_MAX = "100.0"
RISK__QUANTITY_DECIMAL_PLACES = "9"

## universe
UNIVERSE__PRICE_USD_MIN = "5.0"
UNIVERSE__TURNOVER_USD_MIN = "20000000.0"
UNIVERSE__TURNOVER_SESSIONS = "20"
UNIVERSE__LOOKBACK_DAYS = "45"

## portfolio
PORTFOLIO__ORDERS_PER_REQUEST = "500"
PORTFOLIO__LOOKBACK_DAYS = "410"
PORTFOLIO__PENDING_TTL_MINUTES = "5"
PORTFOLIO__OPENING_LEAD_MINUTES = "30"
PORTFOLIO__ITERATION_MINUTES = "1"
PORTFOLIO__STOP_COVERAGE_DRIFT_SHARES_MAX = "0.000001"

## backtest
BACKTEST__WARM_UP_DAYS = "60"
BACKTEST__BUDGET_USD = "100000.0"

## earnings
EARNINGS__BLOCK_DAYS = "5"

## indicators
INDICATORS__PERIOD_BARS = "14"

## breakout
BREAKOUT__RANGE_FRACTION_MIN = "0.004"
BREAKOUT__LONG_STOP_FRACTION = "0.75"
BREAKOUT__MID_FRACTION = "0.5"
BREAKOUT__SHORT_STOP_FRACTION = "0.25"
BREAKOUT__STOP_FRACTION_MIN = "0.01"
BREAKOUT__STOP_FRACTION_MAX = "0.05"
BREAKOUT__TARGET_FRACTIONS = "[0.5, 0.25]"
BREAKOUT__LOOKBACK_SESSIONS = "20"
BREAKOUT__SIGNAL_BARS_MAX = "2"
BREAKOUT__TRAIL_ATR_MULTIPLE = "1.5"
BREAKOUT__TRAIL_BARS_MIN = "15"
BREAKOUT__SCAN_MINUTES = "60"
BREAKOUT__CLOSE_LEAD_MINUTES = "6"
BREAKOUT__CONFIRM_LOOKBACK_DAYS = "45"
BREAKOUT__TRAIL_LOOKBACK_DAYS = "5"

## breakout_5m
BREAKOUT_5M__OPENING_MINUTES = "5"
BREAKOUT_5M__VOLUME_MULTIPLE = "1.3"
BREAKOUT_5M__TARGET_MULTIPLES = "[1.5, 2.5, 4.0]"
BREAKOUT_5M__ENTRY_EXTENSION_MAX = "none"
BREAKOUT_5M__IS_PAUSED = "false"

## breakout_10m
BREAKOUT_10M__OPENING_MINUTES = "10"
BREAKOUT_10M__VOLUME_MULTIPLE = "1.5"
BREAKOUT_10M__TARGET_MULTIPLES = "[2.0, 3.0, 5.0]"
BREAKOUT_10M__ENTRY_EXTENSION_MAX = "0.25"
BREAKOUT_10M__IS_PAUSED = "false"

## breakout_15m
BREAKOUT_15M__OPENING_MINUTES = "15"
BREAKOUT_15M__VOLUME_MULTIPLE = "1.7"
BREAKOUT_15M__TARGET_MULTIPLES = "[1.5, 2.5, 4.0]"
BREAKOUT_15M__ENTRY_EXTENSION_MAX = "0.20"
BREAKOUT_15M__IS_PAUSED = "false"

## daily
DAILY__AVERAGE_SESSIONS = "20"
DAILY__EXIT_RSI_MAX = "50.0"

## daily_sma
DAILY_SMA__TREND_SESSIONS = "50"
DAILY_SMA__TREND_SESSIONS_LONG = "200"
DAILY_SMA__RSI_MIN = "50.0"
DAILY_SMA__ADX_MIN = "25.0"
DAILY_SMA__STOP_ATR_MULTIPLE = "1.5"
DAILY_SMA__HOLDINGS_MAX = "6"
DAILY_SMA__IS_PAUSED = "true"

## daily_20sma
DAILY_20SMA__TREND_SESSIONS = "50"
DAILY_20SMA__TREND_SESSIONS_LONG = "200"
DAILY_20SMA__RSI_MIN = "50.0"
DAILY_20SMA__RSI_MAX = "70.0"
DAILY_20SMA__ADX_MIN = "25.0"
DAILY_20SMA__MARKET_CAP_USD_MIN = "2000000000.0"
DAILY_20SMA__HOLDINGS_MAX = "6"
DAILY_20SMA__ENTRY_MINUTES = "5"
DAILY_20SMA__STOP_FRACTION = "0.05"
DAILY_20SMA__BREAKEVEN_GAIN = "0.10"
DAILY_20SMA__TARGET_GAINS = "[0.15, 0.25]"
DAILY_20SMA__TARGET_FRACTIONS = "[0.5, 0.25]"
DAILY_20SMA__TRAIL_ATR_MULTIPLE = "1.5"
DAILY_20SMA__TRAIL_HOURS = "4"
DAILY_20SMA__TRAIL_LOOKBACK_DAYS = "30"
DAILY_20SMA__IS_PAUSED = "false"

## daily_tfb
DAILY_TFB__TREND_SESSIONS = "50"
DAILY_TFB__TURNOVER_SESSIONS = "20"
DAILY_TFB__ADX_MIN = "20.0"
DAILY_TFB__TREND_LAG_SESSIONS = "3"
DAILY_TFB__STOP_ATR_MULTIPLE = "2.0"
DAILY_TFB__HOLDINGS_MAX = "6"
DAILY_TFB__IS_PAUSED = "true"
```

### Validation rules enforced at startup

- `notional_usd_max ≥ notional_usd_min`
- `positions_max ≥ 2`
- breakout: `stop_fraction_max > stop_fraction_min`; `sum(target_fractions) < 1`
- breakout variation: target multiples strictly rise
- daily_20sma: `rsi_max > rsi_min`; target gains rise; `sum(target_fractions) < 1`
- strategy keys must be distinct; each code is one unique character
- a missing rules field fails at import
