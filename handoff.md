# handoff

## intent

Scrub `money-tree` down to the code that runs, expressed the way
`skills.guides` says to express it, using the libraries already declared.
Destructive by design: drop tests, drop duplication, collapse to library APIs,
fix API misuse. Breakage and stubs were explicitly permitted.

## initiating request (verbatim)

```
--yolo
/deep-scrub
first, drop tests and aggressively drop duplication, redundancy, dead code, and non-compliant /guides code
second, collapse functionality to libraries and apis where possible and consolidate functionality to appropriate modules
third, fix api usage by dropping misconfiguration or misunderstanding of capabilities and access

do not worry about breaking code, temporary stubs are acceptable
do not write new tests and do not worry about logical checks
```

Preceded in the same session by two smaller asks: "pull the latest code", then
"evaluate the code quality". The pull revealed that `origin/main` had been
rewritten — 120 local commits existed there under new SHAs, plus ~92 new
commits (~13k insertions) from parallel cloud agents. Local `main` was reset
onto `origin/main`; the pre-reset state is preserved on the branch
**`local-main-snapshot`**.

## later refinements

None. `--yolo` was in force, so no clarifying questions were asked and no
mid-course corrections were issued. The plan was approved as written at
`/Users/m/.claude/plans/yolo-deep-scrub-first-drop-elegant-teapot.md`.

Two constraints were self-imposed during planning and held throughout:

- `spec.md` treated as **read-only** (the deep-scrub rule forbids editing spec
  unless the request grants spec scope; it did not). Drift was catalogued, not
  fixed.
- `.railway/railway.ts` treated as read-only for the same reason it is
  deploy-state rather than code.

## caution

**I was running out of context, this handoff may contain incorrect assumptions
or damaging biases.** Everything below — especially the "not done" reasoning and
the severity calls — should be re-derived rather than trusted. Three findings in
this session were produced by subagents and two of my own working assumptions
were overturned mid-task (see *corrections* below); assume more are wrong.

## summary

### state

51 files changed, +431 / −7,745 (net −7,314). Python 11,128 → 4,162 lines;
assets 5,333 → 4,920. Nothing is committed — all of this is an uncommitted
working tree on `main`.

Verification at time of writing, all green:

```
ruff check src            All checks passed
ruff format --check src   21 files already formatted
pyright (strict)          0 errors
node --check              dashboard.js, theme.js OK
comment census            0 comments, 0 docstrings under src/
```

Not verified: runtime behaviour. No tests exist any more, and logical checks
were out of scope by instruction. `uv run python -c "import bot.portfolio"`
could not be run in this session because the sandbox denies reading `.env`;
`compileall` and a config-free import sweep passed instead.

### done

- **L0 excise (−5,759).** Deleted `tests/`, `.backtest/`, `src/analysis/`, and 8
  dead API routes. Dropped `pytest`/`arch`/`numpy` dev deps and the pytest
  config block.
- **L1 decomment (−550 py, −418 js/css).** All comments and docstrings under
  `src/`.
- **L2 naming.** 125 renames across 29 names; 38 co-module imports made
  relative; `TC_SIBLINGS` → `TC_COTRADES`.
- **L3 dedupe.** Deleted `daily.py`, `sma.py`, `orb.py`, `orb_momentum.py`,
  `noop.py`, `OrbStrategy`, `DailyStrategy`, `tfb_50.Strategy`, and
  `load_strategy`. `backtest.py` now drives `portfolio.Strategy` with a
  single-strategy parameter list. One implementation per strategy, down from
  three.
- **L5 API.** Added `delayed_sip` to `DataFeedName`/`DATA_FEEDS`; widened all 21
  dependency ranges; collapsed 4 deferred yfinance imports into 2.
- **Two live bugs fixed**: hardcoded `" · Fri 30 Jan"` chart note; a
  `(up ? colour : colour)` no-op.

### corrections made in flight — do not re-inherit the originals

1. **`ui/ledger.py` → pandas was wrong.** `match_cycles` is a stateful
   sequential scan over signed positions closing at a zero crossing, not a
   grouping. A pandas rewrite is longer and slower. The only real cleanup there
   is `bisect.bisect_left` for the O(days²) scan in `sessions`.
2. **"Indicators are hand-rolled" was wrong.** `shared.py` already delegates
   ATR/RSI/MACD/SMA/ADX/cross to `pandas-ta-classic` correctly. What is
   hand-rolled is the wrapper layer (`_finite_value`, `_indicator_series`,
   `_indicator_column`) and rolling-window mechanics.
3. **`ui/alpaca.py` must stay hand-rolled.** alpaca-py's REST client is
   synchronous (`alpaca/common/rest.py:26`); `async def` appears only in
   websocket streaming. Replacing it would block the FastAPI event loop, and
   `/v2/account/activities` has no `TradingClient` method at all.
4. **`cast(Any, import_module("yfinance"))` is load-bearing**, not a pyright
   dodge to delete. yfinance ships no stubs; a plain `import yfinance` fails
   strict mode with ~20 errors. I tried it, reverted it.
5. **`# pyright: ignore[reportCallIssue]` is a pragma, not prose.** The
   decomment pass removed it from `app.py:53` and broke the typecheck; restored.

### known cost of this scrub

The compliance audit read all 219 `src` comments and judged **~85%
load-bearing** — bug provenance, threshold rationale, vendor quirks. The guide
says "code has no comments" without qualification, so they were all stripped.
That knowledge is recoverable only via
`git show local-main-snapshot:src/bot/portfolio.py` and siblings. If any of the
remaining work touches a threshold, read the old comment first.

### not done, roughly by value

1. **Calendar delegation to `exchange-calendars`** — the largest remaining item
   and not merely stylistic. The package is a declared dep used in exactly one
   place, while ~12 sites hardcode `09:30` / `15:59` / `15:54`. On a 13:00
   half-day close, `ORB_CLOSE_DEADLINE = time(15, 54)` never arrives, so **ORB
   positions are never flattened**. Same class of error in `session_volume`,
   which compares full sessions against half sessions in its 20-day average.
2. **`get_orders(..., limit=500)` is unpaginated** (`portfolio.py`) and feeds
   `_restore`'s entry-order lookup. An account past 500 historical orders
   silently loses the oldest.
3. **Order-tag encode/decode in 3 places** — `portfolio.py`, `bot/attribution.py`,
   `ui/ledger.py`. Intended collapse: one `bot/order_tag.py`, delete
   `attribution.py`.
4. **`ui/strategies.py` still re-declares ~20 constants**, 7 of which are
   already importable module constants on the bot side. The test that used to
   pin them died with `tests/`, so this duplication is now unguarded.
5. **`wilder_atr` in `dashboard.py`** is a redundant fourth ATR. Its docstring
   claimed the web process must not pull in the strategy stack; the audit
   disproved that empirically (importing `ui.dashboard` loads 1,606 modules
   including lumibot). Replace with `shared.latest_atr`.
6. **Module splits.** `portfolio.py` is still 1,284 lines / ~50 methods;
   `dashboard.py` 666; `dashboard.js` 2,610. The JS win is the interaction layer
   (`initChartInteraction` vs `wireTradeChart`, ~110 of 288 lines duplicated with
   identical magic numbers), not the drawing layer. ES modules are blocked by
   `_fingerprint_assets`, which rewrites asset URLs only in the HTML.
7. **Fail-fast**: 13 `except Exception` blocks invent recovery for branches spec
   never declares. Sharpest pair was in the now-deleted `daily.py`, but the
   pattern persists in `portfolio.py` (SIP failure silently falls back to IEX,
   which changes the meaning of every turnover floor).
8. **Events naming** — 21 sites, none matching `subject.past_participle`.
9. **Module ordering** — 18 of 34 files violated imports → types → constants →
   surface → private. Untouched.

### open decision for the user

`.railway/railway.ts` still pins `ALPACA_DATA_FEED: "iex"` and still carries
`ALPACA_LIVE_API_KEY` / `ALPACA_LIVE_API_SECRET`, which are **read nowhere in
`src/`**. `delayed_sip` is now reachable in code and needs no subscription;
historical SIP is also free when `end` is ≥15 minutes old. IEX carries ~2.5% of
market volume, so `ORB_TURNOVER_USD_MIN = 20_000_000` currently behaves like an
~$800M floor — roughly 40× tighter than the register intends. The strategy was
backtested on SIP and is executing on IEX. Whether a 15-minute-delayed
consolidated tape beats a live 2.5% slice is a trading call, not a code call.

### next step

Either commit this pass, or continue with the calendar work (item 1), which is
the only outstanding item that is a correctness bug rather than a cleanup.
