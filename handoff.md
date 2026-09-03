# handoff

## intent

Second scrub pass on `money-tree`, run on top of the committed first pass.
Same mandate as before — drop what is dead, collapse duplication onto single
owners, delegate hand-rolled mechanics to declared libraries — plus the one
correctness bug the first pass catalogued and left: hardcoded session clocks.

## initiating request (verbatim)

```
@handoff.md
/solo --yolo
/deep-scrub
```

The prior session's handoff (this file's previous revision) supplied the
context: its "not done, roughly by value" list is what this pass worked from.

## later refinements

None. `--yolo` was in force; no clarifying questions were asked.

Two constraints carried over from the first pass and held again:

- `spec.md` treated as **read-only** — this request granted no spec scope.
- `.railway/railway.ts` treated as read-only, being deploy state.

## summary

### state

15 files changed, +1,350 / −1,527 (net −177). Python 4,162 → 4,022; assets
4,920 → 4,883. Uncommitted, staged, on `main`.

Verification, all green:

```
ruff check src            All checks passed
ruff format --check src   22 files already formatted
pyright (strict)          0 errors
node --check              dashboard.js, theme.js OK
comment census            0 comments, 0 docstrings under src/
```

The net line count understates the change: ~1,100 lines were rewritten rather
than removed. Duplicated *facts* fell much harder than lines did.

Runtime behaviour is still unverified — there are no tests, and `.env` is
unreadable from the sandbox, so nothing that constructs `Settings` was
executed. What *was* executed: every pure function touched, against synthetic
bars, including the half-session cases (see below).

### done

**1. Session clocks now come from `exchange-calendars` (the correctness fix).**
Twelve hardcoded `09:30` / `15:54` / `15:59` / `16:00` literals are gone;
`grep` for a clock literal under `src/**.py` now returns nothing. New surface in
`strategies/shared.py`: `session_bounds`, `upcoming_session_bounds`,
`session_starts`, `session_ends`, `regular_session`.

- `_manage` derives the ORB flatten deadline as `session_close −
  ORB_CLOSE_LEAD_MINUTES`. On the 2024-11-29 half day that is **13:00 − 6min =
  12:54**, where the old `time(15, 54)` never arrived and ORB positions were
  never flattened.
- `session_volume` and the ORB trailing-stop window mask by each row's own
  session bounds instead of `between_time("09:30","15:59")`, so a half session
  is compared as a half session in the 20-day average.
- `on_trading_iteration` returns early when the day is not a session at all.
- The ORB scan window, opening range, and daily earnings exit are all
  session-relative now.

Verified empirically: `session_bounds(2024-11-29)` → 09:30–13:00;
`session_bounds(2024-11-28)` → `None` (Thanksgiving); `session_hour_bars` over
a synthetic half day folds four buckets and drops everything after 13:00.

**2. One order tag.** New `bot/order_tag.py` owns encode and decode
(`order_tag`, `find_order_tag`, `OrderTag`). Deleted `bot/attribution.py`, the
five `_order_*` methods on `Strategy`, and `ledger.order_engine`. Round-trip
tested.

**3. One owner per strategy parameter.** `ui/strategies.py` had re-declared
~20 constants; it now declares none of them. New `strategies/daily_base.py`
mirrors `orb_base.py` and holds `DAILY_STRATEGIES`, `DAILY_STOP_ATR_MULTIPLES`,
`DAILY_EXITS_BEFORE_EARNINGS`, `DAILY_RISK_MAX`. The ORB tables
(`ORB_TARGET_MULTIPLES`, `ORB_ENTRY_EXTENSION_MAX`, `ORB_OPENING_MINUTES`,
`ORB_VOLUME_MULTIPLES`, trail/scan/history constants) moved to `orb_base.py`.
`POSITIONS_MAX`, `POSITION_FRACTION_CAP_MAX` and the three setting defaults
moved to `bot/types.py` and are now read by `Settings`, `portfolio` and both
`ui` modules. Previously-magic literals (`>= 10`, `min(0.10, …)`, `1.5 *
latest_atr`, `len(frame) < 15`, `.tail(20)`) are named.

**4. Delegation.** `wilder_atr` (a fourth ATR) → `shared.latest_atr`;
hand-rolled hour folding → `regular_session` + a pandas `groupby`;
`ledger.sessions` O(days²) scan → `bisect_left`.

**5. Excised.** `is_security_eligible`, `does_macd_confirm` (its only caller
passed `uses_macd=False`), `OrbSetup` (only ever tested for `None` — now the
predicate `is_orb_setup_ready`), `AlpacaReadClient.positions/fills/orders` and
`find_order_strategy_label` (no callers), `DAILY_EXIT_NEEDS_BOTH` and the
`needs_both` branch (both strategies passed `False`), the `uses_macd` /
`ranks_candidates` parameters, `UNCAPPED_RISK_ENGINES`, `Holding.signal`
(identical to `Holding.asset` at every call site), the 16-line `assert` walls in
`does_momentum_enter` / `does_tfb_enter`.

**6. Alpaca API usage.** `_restore` fetched 500 orders blind and matched them
against positions in Python. It now reads positions first and passes
`GetOrdersRequest(symbols=[…held…])`, so the server filters. `alpaca-py` has no
pagination helper (checked in `.venv`); `until` is the cursor, which
`ui/alpaca.py` already uses correctly.

**7. Fail-fast.** Dropped the SIP→IEX fallback in `_daily_bars` — it silently
changed the meaning of every turnover floor — and the `try/except` around
`avg_fill_price`.

**8. Lexicon.** `engine` → `strategy` throughout code *and* register prose
(spec says "strategies"); `asset` → `symbol` on `Holding`; `summarise` →
`totals`; `_minute_of` → `_clock_minute`; `dayOf2` → `dayLabel`. All 21 runtime
event keys are now `subject.past_participle` (`day.loss_reached`,
`orb.capped.{date}`, `stop.passed.{symbol}.{date}`, …). Module ordering
(imports → types → constants → surface → private) fixed in `dashboard.py`,
`ledger.py`, `strategies.py`, `portfolio.py`, `shared.py`, `orb_base.py`.
`report.py` / `trade.py` co-module imports made relative.

**9. `dashboard.js`.** The two pan/zoom rigs (`initChartInteraction` and
`wireTradeChart`, ~110 duplicated lines with identical magic numbers) collapse
into one `wirePanZoom(spec)`. The equity `geo` gained an `indexAt` so both
charts expose the same geometry contract. `TC_VIEW` is now `const` and mutated
through `setTradeView`, because the shared rig captures the object.

**10. One latent bug fixed.** `positionCapPct` reported
`configuration.position_fraction_max` (0.20) when the bot was reporting but
`0.10` when it was not, while the effective cap is `min(0.10, configured)` in
both cases. Now `min(...)` in both branches.

**11. Spec alignment.** `spec.md` lists `events` in the 5-second dashboard
response; the payload carried none. `bot.events` is now in `bot_state`.

### not done

1. **The dashboard still does not render runtime events.** They now reach the
   browser (item 11) but no view consumes them — the "Trade log" is a trade
   log. Building that panel is feature work, not a scrub.
2. **Eleven `except Exception` blocks remain** in `portfolio.py`. The two that
   silently changed meaning are gone; the rest (earnings calendar unreadable,
   universe discovery, intraday bars, trailing-stop refresh) invent recovery
   that `spec.md` does not declare, but each is described in the register, and
   removing them would crash the trading loop on any upstream hiccup. Judgment
   call — re-derive it rather than trusting it.
3. **`portfolio.py` is still 1,065 lines / ~45 methods**; `dashboard.js` 2,573.
   The remaining JS duplication is in the drawing layer, which is genuinely two
   different charts.
4. **`ui/strategies.py` register prose is still hand-written** against the code
   it describes. Nothing pins the two together now that tests are gone; a
   threshold change updates the number but not the sentence around it.
5. **Spec drift, catalogued not fixed** (spec was read-only): `spec.md` still
   lists `analysis/`, `strategies/noop.py`, and a `{name}.py` per strategy, and
   does not list `orb_base.py`, `daily_base.py`, `order_tag.py`, `types.py`,
   `ui/ledger.py`, or `ui/strategies.py`.

### open decision for the user

Unchanged from the last pass, and still the only trading-level question:
`.railway/railway.ts` pins `ALPACA_DATA_FEED: "iex"` and carries
`ALPACA_LIVE_API_KEY` / `ALPACA_LIVE_API_SECRET`, which are **read nowhere in
`src/`**. `delayed_sip` is reachable in code and needs no subscription. IEX
carries ~2.5% of market volume, so `ORB_TURNOVER_USD_MIN = 20_000_000` behaves
like an ~$800M floor. The strategies were backtested on SIP and execute on IEX.
Whether a 15-minute-delayed consolidated tape beats a live 2.5% slice is a
trading call.

Note that the SIP→IEX daily-bar fallback is gone, so a SIP refusal on daily bars
now surfaces as `universe.unavailable` rather than quietly re-screening the
universe on a partial feed.

### next step

Commit this pass. After that the highest-value remaining work is a decision,
not a refactor: either surface runtime events in the UI (item 1) or settle the
data-feed question above.
