# drift

intent: deep scrub of basic issues, vocabulary, duplication, and spec/code drift, 2026-09-08.

fov: repo-owned specification, configuration, source, tests, and packaging; installed engine source for callback and data-source checks. linked agent resources are read-only. secret values, generated reports, and external services are outside the scrub.

layers: config/cli, data/time, strategies, bot, snapshots, web api, dashboard, validation/packaging.

authority: guides and spec precede code and tests. the scan began with edits in 25 files; those edits are preserved. “fixed” describes this scrub, “open” describes an implementation issue, and “decision” describes an incomplete contract.

| name | cat | in spec | in code |
| --- | --- | --- | --- |
| symbols | variable | the collection evaluated by strategies | fixed: `symbols()` and `_symbols` replace `market_symbols`; the spec and rule sheet use the same noun |
| is_market_favorable | function | benchmark close exceeds its average | fixed: replaces the inaccurate `is_benchmark_rising`; the rule sheet calls this the market condition |
| report | function | one replay command | fixed: spec operation is `report`, matching the CLI and implementation; `backtest` remains the configuration section and engine operation |
| trade | function | `trade(strategies)` starts the bot | fixed: replaces module operation `run` and updates the CLI caller |
| risk_fraction_max | variable | strategy override or required account limit | fixed: sizing receives the resolved fraction; removes its unreachable optional-risk branch |
| config_projection | config | each service receives its environment projection | open: importing web settings also instantiates `BotSettings`; the declared web projection does not describe all required runtime config |
| runtime_config | config | environment declares runtime variables | open: `report` writes `LUMIBOT_DISABLE_UI` into `os.environ`; several runtime limits and vendor URLs remain source constants |
| report_inputs | function | replay takes symbols and an ordered date range | open: CLI symbols bypass the `Symbol` validator; CLI date overrides bypass the settings span check |
| bar_sources | pattern | shared past bars; replay uses the engine clock | open: bot bars use configured daily/intraday feeds and `Adjustment.ALL`; web bars use one intraday feed and omit adjustment; daily fills use Yahoo |
| screen_order | function | symbols are in descending turnover order | open: `_screen` sorts alphabetically; strategy candidate ranking later uses descending latest-session turnover |
| report_clock | pattern | daily entries retry every iteration until close | decision: daily replay uses Yahoo's daily price source while the portfolio iterates in minutes; intraday execution fidelity is unspecified |
| first_target_stop | function | first target moves the stop to entry, then trails | open: target handling returns before changing the stop; subsequent handling needs trailing bars before moving it |
| daily_stop | function | stop is entry minus an ATR multiple | open: stop is calculated from the previous close; a fill updates entry and risk but leaves the stop at its prior absolute price |
| partial_fills | function | resting stops protect breakout holdings | open: portfolio handles full fills only; the installed engine's separate partial-fill callback is a no-op |
| restart_state | pattern | one entry per symbol/session; stops never retreat; daily loss uses session-open equity | open: recovery rebuilds only currently held symbols, resets stops from entry risk, and resets the loss baseline at startup |
| emergency_exit | function | cancel orders, exit all, end day | open: only attributed holdings are exited; after locking, later iterations return before management, including holdings arriving through late fills |
| snapshot_order | pattern | signed, bounded snapshots advance in sequence | aligned: same-run sequences must increase; a different run must have a later start; signatures, body size, and heartbeat drift are checked |
| upstream_errors | pattern | broker 429 becomes 503; other upstream errors become 502 | open: task groups wrap HTTP errors in `ExceptionGroup`, which bypasses the registered HTTP-error handler |
| reported_rules | config | dashboard shows the bot's rules and risk limits | open: snapshots carry only account risk; rule rows mix that with web-process strategy settings and position limits |
| exchange_clock | pattern | exchange sessions set trading times | open: rule windows use host `date.today()`; `nextOpen` labels an unconverted timestamp as ET; dashboard close text is fixed at 16:00 |
| history_boundaries | pattern | ledger reconstructs trades from fills | decision: bounded pagination can omit opening fills; position reversals are not split into separate trades |
| exposure_display | variable | exposure is constrained against account equity | open: UI exposure sums signed market values, so short positions can offset long exposure |
| dashboard_ledger | variable | dashboard retains account and trade data | fixed: duplicate `LEDGER` declaration and statistics overwrite are replaced by separate `LEDGER` and `TOTALS` values |
| empty_history | function | dashboard can show an account without trades | fixed: history renders “No closed trades” instead of indexing an empty session list |
| rule_vocabulary | pattern | one name per concept; simple, accurate prose | fixed: symbols/market condition/strategy replace ambiguous labels; stop fractions are measured from the range low; stale calendar-fallback and guaranteed-fill claims are removed |
| theme_token | function | one shared operation per role | fixed: duplicate CSS-token reader is removed; date helpers use `parseDate` and `weekStart` |
| test | function | root has one validation task | fixed: root `test` runs Python lint, formatting, typing, tests, JavaScript syntax, and dashboard regressions; build/deploy depend on it |
| image_inputs | pattern | packaging contains application inputs | fixed: Docker context excludes pytest and Python bytecode caches |

## code issues

### config/cli

- `config_projection`: [settings](src/mt/config/settings.py) constructs the bot singleton at import time; [service projections](src/mt/config/services.py) describe web using `WebSettings` and `LoginSettings`. shared strategy imports make that split incomplete.
- `runtime_config`: [report](src/mt/bot/backtest.py) mutates the process environment. source constants also include vendor URLs, cache headers, and the broker market. classify protocol constants separately from runtime settings before moving them.
- `report_inputs`: [CLI parsing](src/mt/cli/__main__.py) accepts an empty symbol selection, malformed symbols, duplicates, and reversed override dates. failure can occur after creating the run directory or importing the engine.

### data/time

- `bar_sources`: [bot data](src/mt/data/past.py) and [web data](src/mt/data/alpaca.py) can return different prices and volumes for the same symbol/timeframe. chart levels reconstructed from those bars can differ from the bot's levels.
- `history_boundaries`: [pagination](src/mt/data/alpaca.py) returns a bounded prefix without a completeness marker. [cycle matching](src/mt/web/ledger.py) starts from zero quantity and closes only at flat; truncated histories and a fill that crosses through zero need defined treatment.

### strategies

- `first_target_stop`, high: [breakout management](src/mt/strategies/breakout.py) leaves the original stop unchanged after advancing the target stage. an isolated probe with entry 100, stop 98, target 103, and no trailing bars observed stage 1 and stop 98 after two management calls; the spec requires a stop of at least 100.
- `daily_stop`: [daily scanning](src/mt/strategies/daily.py) anchors the stop to the prior close; [fill handling](src/mt/bot/portfolio.py) updates entry without moving that stop. gaps change the realized distance and can violate the stated entry-relative formula.
- `screen_order`: [screening](src/mt/bot/portfolio.py) sorts symbols alphabetically. [candidate ranking](src/mt/strategies/base.py) already implements turnover descending with symbol tie-breaking; decide whether order belongs to the shared symbols or only candidate selection.

### bot

- `partial_fills`, high: [portfolio callbacks](src/mt/bot/portfolio.py) omit `on_partially_filled_order`. the installed Lumibot `Strategy` provides that callback separately from `on_filled_order`, with a no-op default. an entry partially filled for an extended period has no corresponding managed holding or resting stop from this code.
- `restart_state`, high: `_restore` reads orders only for current positions and reconstructs stops from the entry tag. closed trades from earlier in the session are absent from `_traded`; previously advanced stops are not recovered; `_begin_day` uses current equity as its baseline. restarting can permit a repeated entry, retreat a stop, or reset the loss allowance.
- `emergency_exit`, high: `_emergency_exit` cancels orders and exits `_holdings`, not every broker position. it then locks the day. late entry fills are not followed by ordinary management while locked. ownership of unattributed positions and completion of emergency liquidation need explicit handling.
- `report_clock`: [report setup](src/mt/bot/backtest.py) selects `YahooDataBacktesting` for daily strategies. the installed Yahoo source declares `MIN_TIMESTEP = "day"` and reads daily opens for daily last-price requests. a minute loop alone cannot demonstrate the specified intraday retry behavior or exact live next-open fills.

### snapshots

`snapshot_order`: no basic, lexicon, or duplication fix was needed in [the store](src/mt/web/state.py). static inspection covered signature validation, snapshot size, heartbeat/start ordering, same-run sequence rejection, and run replacement. this does not validate concurrent lifecycle behavior or prove delivery of the final exporter snapshot.

### web api

- `upstream_errors`, high: [pulse](src/mt/web/pulse.py) and [ledger](src/mt/web/ledger.py) use task groups; [the app handler](src/mt/web/app.py) handles `httpx.HTTPError`. a mock broker returning 429 produced `ExceptionGroup`, not `HTTPError`, in an isolated pulse probe. the advertised 503/502 mapping does not cover that path.
- `reported_rules`: [rule rendering](src/mt/web/rules.py) takes reported per-trade risk but reads position limits and strategy parameters from local settings. the `configured` label can therefore describe a mixture of bot and web configuration. the ledger cache also retains risk fields until its TTL expires.
- `exchange_clock`: [rule windows](src/mt/web/strategies.py) use the server's calendar date; [ledger formatting](src/mt/web/ledger.py) appends ET without first converting `clock.next_open`. the [dashboard](src/mt/web/assets/dashboard.js) assumes a 16:00 close, including shortened sessions.
- `exposure_display`: [position rows](src/mt/web/pulse.py) retain signed `market_value`, and the dashboard calls the sum deployed value/exposure. the bot's entry checks use absolute values. the same account can show different exposure in these two roles.

### dashboard

`dashboard_ledger` and `empty_history` have regression coverage. `rule_vocabulary` removes inaccurate terms and stale recovery claims without changing strategy execution. `theme_token` removes one duplicate helper. the script still combines account derivation, five views, chart interactions, and polling in one large file; no speculative module split was made.

### validation/packaging

baseline: lint and typing passed; three order-tag tests passed; JavaScript syntax failed on duplicate `LEDGER`; Python formatting flagged four files.

after cleanup: root `test` passes Python lint/format/type checks, three Python tests, syntax checks for both browser scripts, and two dashboard regressions. all four strategy cards have the same ordered rule fields. the mock HTTP and breakout probes above record open defects, not passing acceptance tests. no live orders, deployment, full historical replay, or browser layout test was performed.

## spec sketches

config/cli:

```sketch
config_projection ─→ runtime_config
report_inputs ─→ report · trade
```

data/time:

```sketch
bar_sources ─→ shared past
history_boundaries ─→ complete trades
```

strategies:

```sketch
symbols ─→ screen_order ─→ is_market_favorable ─→ candidates
first_target_stop ─→ entry, then trail · daily_stop ─→ filled entry minus ATR
```

bot:

```sketch
risk_fraction_max ─→ sized entry ─→ partial_fills ─→ protected holdings
restart_state ─→ preserved session and stops · emergency_exit ─→ flat account
report_clock ─→ executable iteration prices
```

snapshots:

```sketch
signed snapshot ─→ snapshot_order ─→ latest run state
```

web api:

```sketch
upstream_errors ─→ 503 or 502 · reported_rules ─→ bot configuration
exchange_clock ─→ session times · exposure_display ─→ gross exposure
```

dashboard:

```sketch
dashboard_ledger ─→ account and trades · empty_history ─→ empty view
rule_vocabulary ─→ canonical names · theme_token ─→ one reader
```

validation/packaging:

```sketch
test ─→ all local checks ─→ build/deploy
image_inputs ─→ application without caches
```

## code sketches

config/cli:

```sketch
config_projection ─→ web imports bot singleton · runtime_config ─→ env plus literals
report_inputs ─→ unvalidated overrides ─→ report · trade
```

data/time:

```sketch
bar_sources ─→ adjusted bot bars, separate web feed, Yahoo fills
history_boundaries ─→ bounded pages ─→ matching assumes flat start
```

strategies:

```sketch
symbols ─→ screen_order alphabetical ─→ candidate turnover ranking
is_market_favorable ─→ benchmark filter
first_target_stop ─→ trailing-data gate · daily_stop ─→ prior-close anchor
```

bot:

```sketch
risk_fraction_max ─→ resolved sizing · partial_fills ─→ inherited no-op
restart_state ─→ current holdings and fresh baseline · emergency_exit ─→ attributed holdings
report_clock ─→ minute loop with daily Yahoo prices
```

snapshots:

```sketch
signed bounded snapshot ─→ snapshot_order ─→ increasing sequence or later run
```

web api:

```sketch
upstream_errors ─→ ExceptionGroup bypass · reported_rules ─→ mixed configuration
exchange_clock ─→ host date and fixed close · exposure_display ─→ signed sum
```

dashboard:

```sketch
dashboard_ledger ─→ LEDGER and TOTALS · empty_history ─→ No closed trades
rule_vocabulary ─→ Symbols and Market condition · theme_token ─→ token()
```

validation/packaging:

```sketch
test ─→ Python and JavaScript checks ─→ build/deploy
image_inputs ─→ cache exclusions
```
