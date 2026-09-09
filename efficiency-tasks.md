# efficiency-tasks

**do not edit spec.**

## Acceptance rules

- consumers reuse compatible successful observations.
- adapters fetch missing coverage and the selected correction overlap.
- portfolio admission rejects exhausted capacity before candidate work.
- consumers refresh data at its required lifecycle boundary.
- transports account for every outbound attempt within their allocated allowance.
- presentation updates only when relevant values change.
- each accepted phase preserves correctness and freshness while reducing both source measurements.

## Responsibilities

| Layer | Responsibility |
| --- | --- |
| Data adapters | Retrieval, pagination, validation, retained observations, and provider request control |
| `Cache` | Reusable values, pending loads, expiry, and invalidation |
| Web builders and routes | Account/history results and HTTP responses |
| Browser | Scheduling, calculations for selected scopes, and presentation |
| Lumibot | Maintained broker positions and orders, including publication |
| `Portfolio` | Ownership, reservations, risk, and final admission |
| Strategies | Setup, eligibility, and management rules |
| Pydantic settings | Required configuration declared once in `mise*.toml` |

The three phases run sequentially. This rewrite is preparation and does not count as a source-reduction phase. Preserve public response fields, strategy keys, order tags, and strategy rules. Exclude UI redesign, new strategy rules, general frameworks, persistent storage, deployment, and unrelated cleanup. Do not write tests or start the trading loop.

The seven original outcomes map to these phases: read reuse to phases 1 and 3; incremental fetching to phases 1 and 2; early rejection to phase 3; refresh frequency to phases 1 and 2; concurrency and retries to phases 1 and 3; changed-output updates to phase 1; correctness and freshness to every affected data and decision path.

## Shared decisions and request control

A full-capacity skip records the existing capacity event and reason. Checks that did not run produce no rejection reasons. Scans may reuse verified observations; admission requires fresh broker reads. Failed retrievals never become empty successful accounts or fresh observations. Protective actions retain their separate execution path.

Use `limits>=5.8`, its moving-window strategy, and process-local memory storage for synchronous and asynchronous request accounting. Keep HTTPX and existing SDK transports. Count actual attempts, including pages and library-initiated requests. SDK clients share the bot allowance. Disable SDK retries explicitly after construction: zero passed to the installed constructor retains its defaults. Use one transport attempt per call. A timed-out submission retains its reservation and client order identity.

Acquire the shared web concurrency permit only when an attempt can proceed; release it after that attempt. Do not hold a permit while waiting for cache work or request allowance. For rate-limit responses, use the later applicable `Retry-After` or supported reset time, with the configured fallback when neither is usable. Normalize timing through the existing error response; the browser retains displayed data during a pause.

Validate replica-weighted trading reads plus actions against the trading ceiling and market-data attempts against the market-data ceiling. The published 200/minute baselines do not establish the deployed subscription. Record endpoint template, operation, status, duration, actual attempts, cache outcomes, and supported allowance metadata through standard logging. Do not log payloads, credentials, or raw identifying URLs.

## Phase 1 — Dashboard observations, history, and presentation

The observation, cache, history, refresh, browser, response, and request-control work is implemented in the working source. Remaining: confirm both source measurements strictly decrease once the source baseline is separated from the concurrent user edits to `dashboard.css`, `dashboard.html`, and the font and vendor assets.

## Phase 2 — Retained bars and daily calculations

### Implementation and interfaces

Use phase 1's cached bar-response construction. Keep synchronous and asynchronous retrieval behind existing bar interfaces. Retain series by symbol, timeframe, feed, adjustment, and source configuration. Track covered intervals separately from returned timestamps; empty intervals are covered only after a successful complete retrieval. Fetch missing coverage and correction overlap, replace overlapping timestamps, deduplicate, validate, and publish only after every required page completes. Preserve SDK pagination; make the asynchronous adapter reject exhausted page allowances. Keep tokens inside adapters.

Retain at most 512 series per adapter using least-recently-used eviction. Bound each retained interval by the largest applicable consumer window derived from existing lookback and chart settings. Do not retain unbounded unions of disjoint historical requests. Requests outside coverage trigger full required reads; eviction never shortens returned results. Reset retained source observations each exchange session. Source/configuration changes invalidate compatible derived results.

Use `_daily_frames`, `_prepared_at`, `_scanned_at`, and `_candidates` as lifecycle boundaries. Compare full raw source inputs, excluding derived columns. Share only identical source, parameters, warm-up, and alignment. Source changes invalidate affected daily candidates.

Daily fetching remains on the preparation/session lifecycle; do not add intraday correction polling. Position management still evaluates prices, earnings, ownership, reservations, and protective conditions at existing boundaries.

### Displaced code and acceptance scenarios

Remove overlapping-window retrieval. Consumer windows must equal full retrieval, including cutoffs and delayed feeds. Repeated reads transfer only required missing/overlap data. Empty coverage and unchanged inputs avoid repeated work. Corrections with unchanged final timestamps invalidate calculations. Both source measurements must decrease from the phase 1 result.

## Phase 3 — Broker observations, admission, and request allocation

### Implementation and interfaces

Extend the existing `alpaca_broker` factory. Capture the fill/publication revision, retrieve positions outside the publication lock, reacquire the lock, and reject snapshots superseded by a revision change. Supply staged positions to Lumibot's existing publication method without another read. Record successful publication and clear staging on every exit. Do not copy Lumibot's algorithm or replace its collection.

Coordinate fills before portfolio callback delivery so a queued callback already invalidates an older snapshot, including quantity changes without membership changes. Split `_fill` and reconciliation into short reservation/ownership mutation sections, followed by `protect`, `exit`, or liquidation outside the synchronization boundary. Do not lock the whole vendor order synchronization method; missing-order handling can make network reads.

Record success/failure at balance, position, and order read boundaries. Failure invalidates reuse even when vendor objects retain values; reaching an iteration proves nothing about synchronization. Broker/portfolio revisions invalidate observations after fills, submissions, cancellations, and reservation changes. Use the configured sixty-second maximum age for scan reuse. Preserve deliberate protection and execution reads. Backtests use the engine's deterministic state without live freshness rules.

Retain `_equity`, `_engine_positions`, `_quantity`, and `last_price` as access points. Reuse compatible held prices/exposure only while quantities, prices, reservations, and validity remain unchanged.

`Portfolio.enter` remains final admission: check eligibility and local exclusions; retrieve fresh required positions/orders; count held and pending symbol union including external holdings; reject full capacity before equity, held-price, and exposure work; retrieve fresh balances/prices for remaining candidates; recheck revisions, ownership, strategy/portfolio capacity, and reservations immediately before reserving. If an intervening change invalidates the decision, return without submitting or looping. Reserve before submission and preserve reservations across ambiguous failures.

Expose the portfolio-capacity calculation to scans; `Strategy.is_capped` retains strategy capacity. Confirm breakout candidates in ranked order and configured batch sizes, stopping later batches at full capacity. Move `_scanned` updates so skipped candidates remain eligible. Retain daily candidates after temporary capacity rejection. Emit existing capacity events and normal rejection reasons only for executed checks.

Share bot request accounting across the portfolio adapter, Lumibot client, and market-data clients. Preserve separate trading-action capacity and reconcile uncertain submissions by existing client order identity.

### Displaced code and acceptance scenarios

Remove repeated scan ownership refreshes, compatible balance/price reads, eager confirmation work, and displaced reconciliation paths. Ownership-only requests cannot grow between 20- and 200-candidate scans. Full capacity causes no candidate price/confirmation requests; released capacity permits later consideration. Partial/completed fills, cancellation, and uncertain submissions preserve pending accounting. Failed observations cannot authorize entry. Fill-during-snapshot replay must preserve newer state and reservations. Both source measurements must decrease from phase 2.

## Configuration

Add settings only when consumed, once in `mise*.toml`, required through Pydantic settings.

| Setting or allowance | Default | Owning phase |
| --- | ---: | --- |
| Retained bar series per adapter | 512 | 2 |
| Bar correction overlap | Selected from applicable consumer window/source settings | 2 |
| Scan observation maximum age | 60 seconds | 3 |

## Measurement and verification

Before each phase, preserve the actual source baseline and existing user edits. Count maintained text source under `src/`, including additions, deletions, settings classes, Python, JavaScript, HTML, CSS, and SVG. Exclude documents, generated artifacts, and binary assets. Count non-whitespace characters and lines containing non-whitespace characters. Moving implementation outside `src/`, shortening meaningful names, and compressing statements do not qualify.

| Evidence | Required result |
| --- | --- |
| Non-whitespace characters | Strict decrease from phase baseline |
| Nonblank lines | Strict decrease from phase baseline |
| Behavior and safety scenarios | All pass |
| Existing project checks | `mise --env development run test` passes |
| Requests or computations | Measured reduction for phase target |
| Displaced implementation | Removed |

Use bounded local replay diagnostics with recorded inputs; do not write tests, start trading, or submit orders. Cover all scenarios above, including failure, correction, out-of-order delivery, and synchronization cases. Review the final diff for layer ownership, existing terminology, library reuse, idiomatic code, configuration ownership, and original scope.

The implementation baseline recounted on 2026-09-09 is **268,611 non-whitespace characters and 8,256 nonblank lines**. No phase is accepted yet.

A zero or positive delta in either measurement leaves the phase unaccepted. Earlier savings cannot compensate. Preserve accepted earlier phases and isolate failed candidates without overwriting user edits. If broker synchronization requires copying vendor code, or a complete phase cannot reduce both counts, record the concrete conflict in at most three lines. Do not weaken safety requirements.

## Review

The plan keeps retrieval in adapters, cache coordination in `Cache`, admission in `Portfolio`, publication in Lumibot, and presentation in the browser. Existing names and interfaces remain authoritative. Use installed pandas, pandas-ta-classic, calendar helpers, HTTP clients, and Lumibot publication; `limits` covers missing request accounting. Review written code against the guides before accepting each phase. The three phases cover the seven original outcomes without strategy changes or unrelated work.

## Current implementation evidence — 2026-09-09

Working source, excluding generated artifacts: **268,351 non-whitespace characters and 8,053 nonblank lines**, against the recorded baseline of 268,611 and 8,256. The tree also carries unrelated user edits to `dashboard.css`, `dashboard.html`, and the font and vendor assets, so this whole-tree delta does not by itself establish phase 1's reduction.

| Phase | State |
| --- | --- |
| 1 | Implemented in the working source; reduction gate not yet separated from user edits |
| 2 | Daily-calculation reuse implemented; retained bar series and coverage tracking outstanding |
| 3 | Single membership read in admission implemented; broker publication, observation validity, admission ordering, and request allocation outstanding |

`mise --env development run test` passes.

The daily-calculation change measured **−702 non-whitespace characters and −42 nonblank lines** across `indicators.py`, `daily.py`, `daily_sma.py`, `daily_tfb.py`, `base.py`, `breakout.py`, `portfolio.py`, `ledger.py`, and `pulse.py`.

Bounded local replay compared every rewritten condition against its previous implementation on generated daily frames: 1,872 cases across 13 row counts, 12 seeds, and 3 drifts, plus 400 forced moving-average cross cases, with 0 mismatches and both outcomes exercised for each of the four conditions. The prepared ATR column equalled recomputation. Screen ranking matched the previous implementation across 40 trials of 12 symbols spanning the price and turnover thresholds, and filtering completed observations at preparation time equalled filtering later in the same session. No repository tests were written, and no trading loop, order submission, service restart, or deployment ran.

### Open risk

A local replay of installed Lumibot reproduced the synchronization gap phase 3 must close: a fill changed an existing position quantity to **2**, then an older snapshot replaced it with **1**. Balance synchronization also retains old values after a failed read. Copying the vendor synchronization method is not an accepted solution.

## References

- [Limits moving-window strategies](https://limits.readthedocs.io/en/stable/strategies.html)
- [Limits asynchronous API](https://limits.readthedocs.io/en/stable/api.html)
- [Alpaca trading allowance](https://alpaca.markets/support/usage-limit-api-calls)
- [Alpaca market-data allowances](https://docs.alpaca.markets/us/docs/about-market-data-api)
- [HTTPX transports](https://www.python-httpx.org/advanced/transports/)
- [Lumibot source](https://github.com/Lumiwealth/lumibot)
- [pandas documentation](https://pandas.pydata.org/docs/)
- [pandas-ta-classic documentation](https://xgboosted.github.io/pandas-ta-classic/)
