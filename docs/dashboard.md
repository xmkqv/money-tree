# Money Tree — dashboard design and layout

A record of the Money Tree web dashboard as of 2 Oct 2026 (commit `1367b2c`). Sources: `spec.md`, `src/mt/web/` (Python server, `dashboard.html`, `assets/dashboard.css`, `assets/dashboard.js`, `assets/theme.js`) and the `DASHBOARD__*` settings in `mise.toml`.

## Contents

1. [Design principles](#1-design-principles)
2. [Architecture](#2-architecture)
3. [Access and security](#3-access-and-security)
4. [HTTP API](#4-http-api)
5. [Data freshness and caching](#5-data-freshness-and-caching)
6. [Visual system](#6-visual-system)
7. [Page layout](#7-page-layout)
8. [Views and panels](#8-views-and-panels)
9. [Equity chart](#9-equity-chart)
10. [Trade chart](#10-trade-chart)
11. [Strategy states](#11-strategy-states)
12. [Formatting rules](#12-formatting-rules)
13. [Accessibility](#13-accessibility)
14. [Responsive behavior](#14-responsive-behavior)
15. [Configuration reference](#15-configuration-reference)

---

## 1. Design principles

From `spec.md`:

- The dashboard fits one display.
- Account, positions, orders and events fit one viewport.
- Only the chart scrolls.
- The dashboard marks every value it does not know. Absent, stale and unavailable values render as such, never as zero.
- Every dashboard number leads to the trade behind it. A trade links to its chart.
- Trade marks rest clear of the candles and lead back to their price.
- An older response never replaces a newer account value.
- The web keeps the last bot state across its own restarts (state lives in Redis with no expiry).
- Every response carries the read instant of its source.

---

## 2. Architecture

### Services

| service | role |
|---|---|
| `money-tree-bot` | trading process; publishes state to Redis every 5 s |
| `money-tree-web` | FastAPI app; serves the dashboard and JSON API |
| Redis | holds `mt:state` (bot status, selection, rules, last 50 events, heartbeat) |
| Alpaca | account, positions, orders, fills, clock, bars, asset names |
| Railway | hosting and OAuth login (production) |

### Server stack

- FastAPI + Starlette, one uvicorn worker.
- `httpx2` async clients for Alpaca trading and market data, with rate limits: 60 reads/min, 60 market-data reads/min, 4 concurrent, 60 s pause after a 429.
- `cachetools` TTL caches with in-flight request sharing (`src/mt/web/cache.py`).
- Upstream HTTP error → 502 "Upstream read failed". Alpaca 429 → 503 "Alpaca read limit was reached" with `Retry-After`.

### Front-end stack

- One static HTML shell (`dashboard.html`). The server fills in `ALPACA {{ BROKER_MODE }}`.
- Lit 3.3.3, served locally as `/assets/lit.min.js`. Uses `html`, `render`, `repeat`, `nothing`, `classMap`, `styleMap`.
- No custom elements. Lit `render()` writes into fixed `id` containers in the shell.
- Charts are hand-built SVG strings. No chart library.
- `theme.js` runs in `<head>` before first paint. `dashboard.js` is an ES module.
- CSS uses cascade layers: `reset, tokens, base, layout, components, utilities`.
- Content-Security-Policy: `default-src 'self'`; scripts, styles, fonts and connections from self only; `object-src 'none'`; `frame-ancestors 'none'`.

---

## 3. Access and security

- Production login: Railway OAuth, then an allow-list of emails (`LOGIN__ALLOWED_EMAILS`).
- Development login: `GET /login` creates a local login.
- Session cookie `money_tree_login`, signed, `SameSite=Lax`, HTTPS-only in production, lifetime 8 hours (`WEB__LOGIN_TTL_SECONDS = 28800`).
- Every route except `/healthz`, `/login` and `/auth/callback` needs the cookie.
  - Page requests without a login → 303 redirect to `/login`.
  - API requests without a login → 401. The front-end then redirects to `/login`.
- Every unsafe method carries `X-CSRF-Token`, compared in constant time with the session token. Only `POST /logout` uses it.
- Logout clears the session and sends `Clear-Site-Data: "cache", "storage"`.

---

## 4. HTTP API

All data responses are `{ "data": …, "read_at": <ISO instant> }`.

| route | returns | server cache | client max-age |
|---|---|---|---|
| `GET /healthz` | `{status: ok}` | — | no-store |
| `GET /login`, `GET /auth/callback` | redirects | — | no-store |
| `GET /` | dashboard HTML | — | `private, no-cache` |
| `GET /assets/{file}` | static files | — | default |
| `GET /api/session` | CSRF token, `refresh_seconds` (30), `snapshot_seconds` (10), `stale_seconds` (20), `sma_colors` | — | no-store |
| `GET /api/ledger` | full ledger (below) | 60 s | 10 s |
| `GET /api/snapshot` | account, positions, open orders | 10 s (shared account read) | 0 |
| `GET /api/bars?symbol&timeframe&opened&closed` | chart bars, SMAs, asset name | 120 s, 64 entries | 60 s |
| `GET /api/levels?symbol&strategy_key&side&entry&opened` | range, stop, targets | 120 s, 64 entries | 300 s |
| `GET /api/strategies` | rule cards | — | 60 s |
| `POST /logout` | 204 | — | no-store |

### Ledger payload

- Snapshot fields: `equity`, `cash`, `buyingPower`, `marketValue`, `unrealized_pnl`, `positions`, `orders`, `readAt`.
- `positions[]`: symbol, side, quantity, entry, last, value, unrealized P&L ($ and %), weight (% of equity), `strategy_key`, `entered_at`, `fills`.
- `orders[]`: symbol, side, quantity, type, limit, stop, status, `strategy_key`, `reason`.
- `trades[]`: symbol, side, strategy, quantity, entry, exit, P&L, date, minute, `entered_at`, duration, `fills[]` (date, minute, price, quantity, side in/out, reason).
- `days[]`: date, P&L, trades, wins, equity before the day.
- `totals`: trade count, wins, net P&L, gross profit, gross loss (positive magnitude).
- `periods`: `W` (Monday-to-date) and `M` (month-to-date), each with `start`, `baseline`, `benchmarkPct`, `equityIndex`.
- `equityDaily[]`: one year of daily equity (`1A` period, `1D` timeframe) plus today's live value.
- `invested`: the first non-zero daily equity (funding amount).
- `accountNumber`, `isMarketOpen`, `nextOpenAt`, `nextCloseAt`, `today`, `benchmarkSymbol`.
- `strategies[]`: key, short name, long label (plus `unattributed`).
- `bot`: status, `isStale`, `isRunning`, `isReported`, `reportedAgoMinutes`, `selection` per strategy, `events` (newest first).
- `windows`: each strategy's entry window for the next session.
- `positionCapUsd` (100), `dailyLossLimitPct` (2).

### Bars request

| timeframe | source | pad days | max span | warm-up days |
|---|---|---|---|---|
| `5Min` | 5Min bars, regular session only for stocks | 1 | 10 | 5 |
| `1Hour` | 30Min bars folded into session-aligned hours (09:30, 10:30, …) | 7 | 90 | 46 |
| `1Day` | 1Day bars | 120 | 900 | 300 |

- Window: display from `max(opened − pad, closed + pad − max span)` to `closed + pad`. Data starts `warm-up` days earlier so SMAs have history. `displayFromAt` marks where display starts.
- SMAs: 20, 50, 200 on the returned bars.
- Crypto and options use native hours.

### Levels request

| strategy | levels |
|---|---|
| breakout_* | opening range (high, mid, low) from 5Min bars of the entry session, stop at 0.75 / 0.25 of the range, three targets at R multiples |
| daily_sma, daily_tfb | stop = entry ∓ ATR multiple × ATR14 of the 90 days before entry |
| daily_20sma | stop = entry × 0.95; targets at +15% and +25% |
| unattributed or non-stock | none |

### Strategies payload

- Card list: a "Market" card for top-level values, then one card per rules section (Broker, Bars, Risk, Universe, …, Breakout family, Breakout 5m, …, Daily 20SMA).
- Each row: label, bound (`≥` / `≤`), formatted value, env var name.
- Labels drop `is`/`does`, `usd` and unit words; units become suffixes (`min`, `h`, `sess`, `days`, `bars`, `×`).
- Fractions show as %, money as `$20M` / `$2B`, flags as yes/no, `None` as `—`.
- `isReported`: true when the rules came from the bot's published state, false when from the web's own environment.

---

## 5. Data freshness and caching

### Polling

| read | interval |
|---|---|
| `/api/snapshot` | every 10 s while the tab is visible |
| `/api/ledger` | every 30 s, or after `Retry-After` when paused |
| on tab return | immediate snapshot and ledger |

### Ordering rules

- The client keeps the newest account `read_at` seen.
- A snapshot older than that is ignored.
- A ledger older than the last snapshot keeps its trades but takes account fields from the snapshot.
- A snapshot whose position symbols differ from the ledger's forces a ledger refresh (the server also drops its cached ledger).
- Chart and levels responses that arrive after the user moved on are dropped.

### Staleness

- Feed stale: last account read older than 20 s, or a failed read after the last success → status dot turns red, text `feed unavailable · read d Mon HH:MM ET`.
- Bot stale: heartbeat older than 15 s (`WEB__HEARTBEAT_TIMEOUT_SECONDS`) → amber dot and a "Bot last reported N min ago" note. Strategy badges show the last reported state with a stale mark.
- No bot state ever → "Bot has never reported"; selections read `unknown`.

### Re-rendering

- If trades, strategies, days, periods, invested, benchmark, today, totals, windows or daily equity changed → full re-render.
- Otherwise only the live account figures repaint.
- Views render on first visit. Chart redraws go through `requestAnimationFrame` and skip when inputs are unchanged.

---

## 6. Visual system

### Typefaces

| role | font | notes |
|---|---|---|
| UI | Archivo (variable, weight 100–900, width 62–125%) | headings use narrow width (88%) and tight tracking |
| Data | Spline Sans Mono (weight 300–700) | all figures; `tabular-nums` |

Both are self-hosted `.woff2` files and preloaded.

### Color tokens (oklch, `light-dark()` pairs)

| token | light | dark | use |
|---|---|---|---|
| `--canvas` | 97% 0.003 264 | 15.8% 0.007 258 | page background |
| `--surface` | 100% 0 0 | 21.3% 0.013 264 | panels |
| `--surface-2` | 97.6% 0.003 264 | 23.8% 0.015 262 | inset areas |
| `--surface-3` | 94.3% 0.007 268 | 28.4% 0.018 262 | pressed controls, pills |
| `--ink` | 20.9% 0.010 268 | 96.6% 0.005 258 | primary text |
| `--ink-2` | 50.1% 0.022 258 | 73.5% 0.020 258 | secondary text |
| `--ink-3` | 56.7% 0.022 260 | 60.1% 0.021 258 | labels, eyebrows |
| `--gain-mark` / `--gain-ink` | green, hue ~159 | | positive values, targets |
| `--loss-mark` / `--loss-ink` | red, hue ~21 | | negative values, stops, loss limit |
| `--hold-mark` / `--hold-ink` | amber, hue ~70–79 | | warnings, stale bot |
| `--flat-ink` | grey | | zero values |
| `--accent` / `--accent-mark` | blue, hue ~226–232 | | focus ring, live dot |

- Rules and grids are the ink color at 6–31% alpha (`--rule`, `--rule-strong`, `--rule-week`, `--grid`, `--grid-zero`, `--crosshair`).
- In dark mode panels get a faint 7.5% white border instead of shadows.

### Strategy hues

Each strategy has a hue; marks render as `oklch(var(--mark-l) var(--mark-c) hue)` with lightness 55% / chroma 0.16 (light) and 63% / 0.163 (dark).

| strategy | hue |
|---|---|
| breakout_5m | 256 (blue) |
| breakout_10m | 77 (amber) |
| breakout_15m | 122 (yellow-green) |
| daily_sma | 287 (violet) |
| daily_tfb | 352 (pink-red) |
| daily_20sma | 170 (teal) |

SMA line hues: SMA 20 → 204, SMA 50 → 300, SMA 200 → 38.

### Density scaling

- `--t-h` = clamp(0, (viewport height − 42rem) / 10rem, 1).
- `--density` = 0.68 + 0.32 × `--t-h` scales all spacing and radii.
- `--type-density` = 0.92 + 0.08 × `--t-h` scales type.
- Short screens compress smoothly; screens 52rem+ tall use full size.
- Phone (`width < 45em`): density 0.86, type density 1.

### Scales

- Spacing: 3xs 0.125rem, 2xs 0.25, xs 0.375, sm 0.5, md 0.75, lg 1, xl 1.5, 2xl 2 (× density).
- Radii: xs 0.1875rem, sm 0.375, control 0.625, cell 0.75, panel 1rem (× density), pill 999px.
- Type: fluid `clamp()` sizes from 3xs (~0.47–0.56rem) to 2xl (~1.25–1.69rem).
- Motion: 160 ms fast, 120 ms snap, easing `cubic-bezier(0.2, 0, 0.3, 1)`.
- Shadow: `0 1px 2px` + `0 6px 18px` at 4–5% alpha (light mode only).

### Components

- **Panel**: surface background, panel radius, soft shadow, `container: panel` for container queries. Head row with `h2` and a mono uppercase eyebrow.
- **Segmented control**: pill group; pressed button uses `--surface-3`.
- **Status pill**: mono text, pulsing dot (2.6 s), separators.
- **Meter**: thin bar with `--meter-fill`; strategy meters use the strategy hue.
- **Chip**: small swatch in the strategy hue before strategy names.
- **Side badge**: `L` / `S`.
- **Calendar cell**: tinted by P&L size.
- **Favicon**: black broadleaf-tree silhouette (inverts to light on dark tab strips).

---

## 7. Page layout

### Desktop (≥ 64em wide and ≥ 36em tall)

The page fills the viewport. The body does not scroll. Max width 115rem, centered.

```
┌───────────────────────────────────────────────────────────────────────────┐
│ Money Tree ☀☾ [ALPACA PAPER]  Dashboard Portfolio History▾ Strategies Sign out │
│ ● Market open · closes 16:00 ET · Account … · N positions · read … · bot … │
├──────────────────────┬────────────────────────────────────────────────────┤
│ Account value        │ Equity chart                               (42%)   │
├──────────────────────┤                                                    │
│ Performance          │                                                    │
├──────────────────────┼─────────────────────────┬──────────────────────────┤
│ Strategies   (2fr)   │ Today / session  (1fr)  │ Calendar        (1.12fr) │
├──────────────────────┤                         │                   (58%)  │
│ Orders       (1fr)   │                         │                          │
├──────────────────────┤                         │                          │
│ Events       (1fr)   │                         │                          │
└──────────────────────┴─────────────────────────┴──────────────────────────┘
   rail: minmax(18.5rem, 3.3fr)        stage: 8.7fr
```

- Top bar: brand, theme toggle, mode pill, tab nav, status pill. Wraps when narrow.
- Grid: rail `minmax(18.5rem, 3.3fr)`, stage `8.7fr`.
- Rail rows: `auto auto 2fr 1fr 1fr`.
- Stage rows: 42 / 58. Bottom row splits 1 : 1.12.
- Panels scroll inside themselves; the page does not.
- The Portfolio, Overview, Trades, Strategies and Chart views scroll the page.

### Narrow or short (< 64em wide or < 36em tall)

- One column. The page scrolls.
- Equity chart height `min(18.75rem, 40svh)`.
- Bottom panels `min(25rem, 60svh)` each.

### Phone (< 45em wide)

- Sticky top bar. Tabs move to a fixed bottom bar (safe-area aware).
- Every grid becomes one column.
- Tables marked `data-cards` turn into cards; each cell shows its header as a label.
- The equity chart is hidden and replaced by a note.
- The trade chart stays and supports pinch zoom.

---

## 8. Views and panels

Routing is hash-based with `pushState`:

| hash | view |
|---|---|
| (none) | Dashboard |
| `#portfolio` | Portfolio |
| `#overview` | History → Overview |
| `#trades` | History → Trades |
| `#strategies` | Strategies |
| `#chart?from=<view>&symbol=<SYM>&entered=<iso\|open>` | Trade chart |

A deep link to a chart inserts the origin view into history first, so Back returns there.

### Shared table rules

- One builder draws every table. Numeric columns right-align.
- The symbol is a button ("Chart this trade") when a trade exists. Otherwise plain text.
- Side badge `L` / `S` follows the symbol.
- Strategy cells show the hue chip and short name; the full label is the tooltip.
- No sorting or pagination. Only the symbol is clickable.
- Empty tables show one message row.

### 8.1 Dashboard

**Account value** (eyebrow "USD")
- Portfolio (equity), Cash.
- Tiles: Total return ($ and %), Last session ($ and %), Open positions, Exposure (market value ÷ equity), Daily loss limit ("x.xx% of 2.00%" with a red meter), Position cap ("$largest of $100" with a meter).
- Drawdown = lowest equity seen in the browser today vs the last daily equity before today.

**Performance**
- Win rate % with a two-part wins/losses bar.
- "Period returns vs SPY": Week and Month cells, each with the period return and SPY's return. `%` / `$` toggle.

**Strategies** (W / M toggle)
- Columns: Strategy, Trades, P&L. P&L shows $ and % of the period baseline. No trades → "—".
- Two badges per row: selection (Online / Paused / Unselected / Unknown) and session (Open / Closed for the entry window).
- The Unattributed row hides when it has no trades.

**Orders** (eyebrow "Open")
- Columns: Symbol, Side, Qty, Kind, Price, Status, Strategy.
- Kind = reason label without "hit" (e.g. "Trailing stop"), else the order type.
- Price = stop / limit.
- Empty: "No open orders."

**Events** (eyebrow "Bot")
- Columns: Time, Level, Message, Strategy.
- Levels colored: info grey, warning amber, error red.
- Empty: "No events reported." or "The bot has not reported."

**Equity** — see section 9.

**Today**
- Title: "Today", "Last session" or "Session", with the date. "Back to latest" when an older day is selected.
- Tabs: Closed N / Open now N.
- Closed: summary (Realized, W of N won, Return); columns Time, Symbol, Strategy, Entry, Exit, P&L.
- Open now: summary (Unrealized, Deployed, Exposure, Largest of cap); columns Symbol, Strategy, Entry, Last, Value, Unreal.

**Calendar**
- Month stepper ‹ ›, bounded by the first month with equity and the current month.
- Summary: Trades, Wins, P&L, Return.
- Columns Mon–Fri plus a week Total.
- Each day: date, $ and %. Tint strength = |P&L| ÷ the month's largest day (7–26% light, 9–30% dark).
- Click or Enter/Space selects the day for the Today panel.
- Legend: Loss / No trades / Gain. "Tint depth tracks the size of the day's P&L."

### 8.2 Portfolio

- Account block: Market value, Cash, Unrealized, Positions, Exposure, Largest %, Buying power, Position cap.
- **Allocation** by strategy: chip, name, position count, $ value, % of deployed, hue meter.
- **Position weight** vs the $100 cap: per symbol "x.x% · $value", meter = value ÷ cap; rows near the cap are marked.
- **Open positions**: Symbol, Strategy, Opened, Quantity, Entry, Last, Value, Weight, Unrealized ($ and %).
- **Previous session**: Time, Symbol, Strategy, Quantity, Entry, Total entry, Exit, Total exit, P&L.

### 8.3 History → Overview

- Totals tiles: Realized P&L, Trades (N sessions), Win rate (W / L), Profit factor (profit ÷ loss), Expectancy (per trade), Average win, Average loss, Payoff ratio (avg win ÷ avg loss), Best trade, Worst trade.
- By strategy: net P&L, "N trades · win % · PF".
- Session P&L: a bar strip (one bar per session, min height 2% of peak) and a table: Session, Trades, Won, Lost, Win rate, P&L, Return. Newest first; each session has sub-rows per strategy.

### 8.4 History → Trades (trade log)

- Filters: Strategy, Side (All / Long / Short), Result (All / Wins / Losses; loss = P&L ≤ 0), Session, Symbol (substring), Clear.
- Count line: "N trades", or "N of M · ±$ · x.x% won" when filtered.
- Columns: Date, Entry time, Exit time, Symbol, Strategy, Quantity, Entry, Total entry, Exit, Total exit, P&L.
- Overnight holds get a day badge. Rows band by day; a heavier rule marks week changes.

### 8.5 Strategies (configuration)

- Eyebrow: "Reported by the bot" or "From the mode environment".
- One card per rules section, with chip, name and state badges. Non-online strategies dim.
- Rows: label, bound in italics, value. Hover shows the env var name. Footer shows the namespace (e.g. `BREAKOUT_5M__*`).

---

## 9. Equity chart

- Plots cumulative P&L: equity − funded amount.
- SVG area + line, split at zero: green gradient above, red below. Dashed zero line.
- Y ticks: "nice" steps (~3 ticks), whole-dollar labels, 14% padding. About 6 date labels.
- A dot marks the last point.
- Hover: crosshair, dot, tooltip (date, ±$, % from view start).
- Hero line: big ±$ value, "±x.xx% over view", date range, "Funded $x · d Mon".
- W / M presets start at the period's baseline index.
- Interaction: drag pans, wheel zooms (×1.14, min 3 points), drag the price axis to stretch Y (180 px travel), double-click resets. Panning un-presses W / M.
- Hint: "drag · scroll to zoom · double-click resets".
- A screen-reader table mirrors the data.

---

## 10. Trade chart

Opened from any linked symbol.

### Header

- "← <origin view>" back button.
- Symbol and company name; sub-line with strategy, side and "Open" if still held.
- "‹ i of N ›" stepper through trades in the same symbol (hidden for fewer than 2).
- Bar size toggle: 5 min / 1 hour / Day.

### Facts row

- Entry (or Average entry, "N entries · first …").
- Exit (or Average exit / Last, "N exits · last …" or "still open").
- Quantity.
- Held (or Held so far): `Nd`, `Hh Mm` or `Mm`.
- P&L (or Unrealized) with the direction-adjusted % move.
- Open trades add: "This position is still open. The Now mark is the current price, not an exit, and the figure beside it is unrealized P&L."

### Overlay toggles

- Averages: SMA 20, SMA 50, SMA 200 (disabled with "Not enough bars at this size").
- Levels: Opening range, Targets (disabled with "Breakout trades only"), Stop (disabled with "Not reconstructable").
- Note: "Stop and targets are reconstructed from the rules."

### Drawing

- X axis = bar index, so closed hours leave no gaps. Vertical grid lines at day boundaries. No session shading. No volume.
- Candles: wick line + body; body width = clamp(step × 0.62, 1.5, 9) px; up when close ≥ open.
- Y range covers visible highs/lows, trade and fill prices, visible levels and SMAs, plus 10% padding.
- X labels: intraday "Mon 5 Oct" + "HH:MM"; daily "Mon 5 Oct", switching to "Oct 2026" when crowded.
- SMA lines in their hues, length number at the right end, end labels kept ≥ 12 px apart.
- Levels:
  - opening range: shaded band; Range high / low dashed `4 3`, Range mid `2 4`
  - Stop: dashed `5 4`, loss color
  - Target N: dotted `1 4`, gain color
  - labels at the left with a halo

### Trade marks

- One point per fill: entry (`in`) fills and exit (`out`) fills. An open trade adds a "Now" point at the last price. Each point snaps to the nearest bar.
- SVG: dotted horizontal hint line at each price; dashed leg from the first entry to each exit, colored by outcome; entry circle r 5.5; exit circle r 6, filled green or red.
- HTML label boxes (`.tc-mark`) with a 3 px strategy-colored left border:
  - title: Entry / Exit / Now + strategy short name
  - price
  - reason: Stop hit, Breakeven stop hit, Trailing stop hit, Target 1/2/3 hit, End-of-day exit, Exit signal, Earnings exit, Daily loss limit
  - detail: entry "X sh · $notional"; exit "N% sold · ±$"; now "X sh held · ±$"
- Placement (keeps labels off the candles):
  1. Flip left when the label would cross the right edge.
  2. Take the high–low band of bars within ±3 bars; place the label 10 px above or below it, on the side with more room.
  3. Resolve overlaps: higher price above, lower price below, then stack downward.
  4. Draw a dashed leader line (`2 3`) from the price point to the label's nearest edge.

### Interaction

- Tooltip: date, time, close, Open, High, Low.
- Wheel zoom ×1.14 about the cursor (min 4 bars), drag pans, price-axis drag stretches Y, pinch zoom on touch, tap (< 8 px travel) shows the tooltip, double-click resets.
- Redraw on resize after 80 ms.
- Loading / error text: "Loading 5 min bars…", "Historical bars could not be read. Try again in a moment.", "No historical bars are available for this window."
- Notes: "Each entry and exit order has its own mark", "The figures above the chart are averages", "Historical bars do not show the final trailing stop."

---

## 11. Strategy states

### Selection badge

| state | meaning (tooltip) |
|---|---|
| Online | selected and can open positions |
| Paused | manages existing positions, opens no new ones |
| Unselected | not selected; existing positions still managed |
| Unknown | the bot has not reported its selection |

When the bot is stale the badge shows the last reported state and adds "last reported state; the bot has stopped reporting".

### Session badge

- **Open**: market open and now is inside the strategy's entry window — "Inside its entry window — it can open a trade now".
- **Closed**: otherwise — "Outside its entry window — no new trade will start".
- The tooltip includes the window, e.g. "09:35–10:30 ET".

### Status-bar bot note

- "Bot has never reported"
- (empty while running and fresh)
- "Bot <status>" (starting / stopped / failed)
- "Bot last reported under a minute ago" / "Bot last reported N min ago"

---

## 12. Formatting rules

| kind | rule |
|---|---|
| unknown number | `—` (em dash), never 0 |
| currency | en-US, 2 decimals (`usd`), 0 decimals on axes (`usd0`) |
| signs | `+` and `−` (U+2212) before the absolute value |
| percent | 1 decimal; signed percent 2 decimals |
| shares | up to 4 decimals |
| tone | > 0 green, < 0 red, 0 grey |
| unavailable % | baseline 0 or absent → `—` |
| time zone | America/New_York for every time |
| clock | 24-hour (en-GB) |
| dates | "5 Oct", "Mon 5 Oct", "Mon 5 Oct 2026", "Mon 5 Oct 26" (trade log) |
| funding unknown | "Funded —" |

---

## 13. Accessibility

- `role=status` on the status pill and tooltips.
- `aria-pressed` on segmented controls and theme buttons; `aria-current="page"` on the active tab.
- History menu: `aria-haspopup`, `aria-expanded`, closes on Escape or outside click.
- Calendar cells: `role=button`, `tabindex=0`, aria-label, Enter/Space; the calendar has a caption.
- Charts: SVG `role=img` with aria-label, plus `.sr-only` data tables or lists.
- `:focus-visible` 2 px accent outline.
- `prefers-contrast: more`: secondary inks become primary ink; stronger panel borders.
- `forced-colors`: system borders on controls, meters and badges.
- `prefers-reduced-motion`: no pulse, no cell hover motion, no meter transitions.

### Theme

- Two buttons: light (sun) and dark (moon). No "system" button.
- With nothing saved, the page follows `prefers-color-scheme` and tracks changes.
- A choice saves to `localStorage["mt-theme"]` (wrapped in try/catch) and sets `<html data-theme>`. `theme.js` applies it before first paint.

---

## 14. Responsive behavior

| condition | behavior |
|---|---|
| ≥ 64em wide and ≥ 36em tall | fixed one-screen grid; panels scroll internally |
| < 64em wide or < 36em tall | single column, page scrolls |
| < 45em wide (phone) | sticky top bar, bottom tab bar, card tables, equity chart hidden |
| < 45em wide and < 33em tall | further compaction |
| trade-chart panel < 56rem | overlay rail moves above the chart |
| chart panel < 44rem | chart hint hidden |
| panel < 30rem | compact panel layout |

---

## 15. Configuration reference

From `mise.toml`.

```toml
## requests
REQUESTS__WEB_READS_PER_MINUTE = "60"
REQUESTS__WEB_MARKET_DATA_PER_MINUTE = "60"
REQUESTS__WEB_CONCURRENCY_MAX = "4"
REQUESTS__PAUSE_SECONDS = "60"

## web
WEB__LOGIN_TTL_SECONDS = "28800"
WEB__HEARTBEAT_TIMEOUT_SECONDS = "15"

## export (bot → Redis)
EXPORT__INTERVAL_SECONDS = "5"
EXPORT__EVENTS_MAX = "50"
EXPORT__CLOSE_TIMEOUT_SECONDS = "5.0"

## dashboard
DASHBOARD__HISTORY_OVERLAP_DAYS = "7"
DASHBOARD__LEDGER_TTL_SECONDS = "60"
DASHBOARD__SNAPSHOT_TTL_SECONDS = "10"
DASHBOARD__CHART_TTL_SECONDS = "120"
DASHBOARD__CHART_CACHE_MAX = "64"
DASHBOARD__NAME_TTL_SECONDS = "86400"
DASHBOARD__NAME_CACHE_MAX = "512"
DASHBOARD__LEVELS_LOOKBACK_DAYS = "90"
DASHBOARD__LEVELS_SOURCE = "5Min"
DASHBOARD__LEVELS_SOURCE_BARS_MAX = "10"
DASHBOARD__BARS_MAX = "1000"
DASHBOARD__CHART_TIMEFRAMES = """{"5Min": {"pad_days": 1, "span_days_max": 10, "warm_up_days": 5}, "1Hour": {"pad_days": 7, "span_days_max": 90, "warm_up_days": 46}, "1Day": {"pad_days": 120, "span_days_max": 900, "warm_up_days": 300}}"""
DASHBOARD__SESSION_SOURCE = "30Min"
DASHBOARD__SESSION_SOURCE_BARS_MAX = "1000"
DASHBOARD__SESSION_SOURCE_PAGES_MAX = "6"
DASHBOARD__PAGE_ROWS_MAX = "100"
DASHBOARD__PAGES_MAX = "40"
DASHBOARD__FLAT_QUANTITY_MAX = "0.000000001"
DASHBOARD__EQUITY_DAILY_PERIOD = "1A"
DASHBOARD__EQUITY_DAILY_TIMEFRAME = "1D"
DASHBOARD__EQUITY_DAILY_TTL_SECONDS = "86400"
DASHBOARD__SMA_LENGTHS = "[20, 50, 200]"
DASHBOARD__SMA_COLORS = '["--sma-1-h", "--sma-2-h", "--sma-3-h"]'
DASHBOARD__LEDGER_MAX_AGE_SECONDS = "10"
DASHBOARD__CHART_MAX_AGE_SECONDS = "60"
DASHBOARD__LEVELS_MAX_AGE_SECONDS = "300"
DASHBOARD__STRATEGIES_MAX_AGE_SECONDS = "60"
DASHBOARD__REFRESH_POLL_SECONDS = "30"
DASHBOARD__SNAPSHOT_POLL_SECONDS = "10"
```

Secrets (not stored in the repo): `BROKER__API_KEY`, `BROKER__API_SECRET`, `FINNHUB__API_KEY`, `WEB__LOGIN_SECRET`, `REDIS__URL`, `LOGIN__OAUTH_CLIENT_SECRET`, `LOGIN__ALLOWED_EMAILS`.
