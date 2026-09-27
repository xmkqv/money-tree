# add strategy: allocation_baa (Bold Asset Allocation)

Add a new strategy `allocation_baa` to the bot. Follow the path `daily_20sma` takes through
the code (`rules/values.py`, `rules/sections.py`, `rules/settings.py`, `strategies/`,
`strategies/registry.py`, `mise.toml`, `spec.strategies.md`). Read `spec.md` and
`spec.strategies.md` first. Do not write tests. Run `mise run test` at the end.

## source

- Keller (2022), "Relative and Absolute Momentum in Times of Rising/Low Yields: Bold Asset
  Allocation (BAA)", SSRN 4166845
- tracked live by AllocateSmartly since 2015 (out-of-sample)
- check each rule below against the paper before coding; the paper wins on any conflict

## rule (BAA aggressive, G4)

```
universes
    canary     = SPY, EFA, EEM, AGG            (read only, never held)
    offensive  = QQQ, EEM, EFA, AGG            (hold top offensive_top = 1)
    defensive  = TIP, DBC, BIL, IEF, TLT, LQD, BND  (hold top defensive_top = 3)
    cash       = BIL

momentum (month-end closes from the daily frame)
    13612W = (12 * r1 + 4 * r3 + 2 * r6 + r12) / 4     r_n = n-month total return
    SMA12  = p0 / mean(p0 .. p12) - 1                  13 month-end closes

regime
    any canary 13612W < 0 (breadth = 1) → risk-off, else risk-on

selection
    risk-on  → top offensive_top offensive assets by SMA12
    risk-off → top defensive_top defensive assets by SMA12;
               a pick with SMA12 below BIL's SMA12 → replace with BIL
    equal weight across picks

rebalance
    first session of each month, entry_minutes after the open
    exit holdings no longer picked (reason "signal"), then enter new picks
    unchanged picks stay untouched
```

The aggressive G4 universe excludes SPY from holdings, so it never collides with
`intraday_mim` on SPY. The balanced G12 universe (SPY, QQQ, IWM, VGK, EWJ, EEM, VNQ, DBC, GLD,
TLT, HYG, LQD; top 6) is a settings change to the symbol lists and `offensive_top`.

## identity

- key `allocation_baa` → family `allocation`, variation `BAA`
- order code `b` (unused; existing codes are o, m, f, s, t, w)
- `holdings_max = 3`

## settings (`ALLOCATION_BAA__*` in mise.toml)

```
ALLOCATION_BAA__CANARY_SYMBOLS = '["SPY", "EFA", "EEM", "AGG"]'
ALLOCATION_BAA__OFFENSIVE_SYMBOLS = '["QQQ", "EEM", "EFA", "AGG"]'
ALLOCATION_BAA__DEFENSIVE_SYMBOLS = '["TIP", "DBC", "BIL", "IEF", "TLT", "LQD", "BND"]'
ALLOCATION_BAA__CASH_SYMBOL = "BIL"
ALLOCATION_BAA__OFFENSIVE_TOP = "1"
ALLOCATION_BAA__DEFENSIVE_TOP = "3"
ALLOCATION_BAA__BREADTH = "1"
ALLOCATION_BAA__ENTRY_MINUTES = "15"
ALLOCATION_BAA__STOP_FRACTION = "0.25"
ALLOCATION_BAA__HOLDINGS_MAX = "3"
ALLOCATION_BAA__IS_PAUSED = "false"
```

Add `allocation_baa` to `STRATEGIES`.

## fit with the existing code

- `Portfolio._universe` keeps common stocks only. Reuse or add the fixed-symbol hook
  (a strategy classmethod `symbols()` whose symbols `Portfolio._prepare` adds to `requested`);
  BAA declares canary ∪ offensive ∪ defensive ∪ cash
- momentum reads month-end closes from `portfolio.daily_frame`. SMA12 and r12 need about
  13 months; `PORTFOLIO__LOOKBACK_DAYS` is 390. Raise it to 420 if the frame is short
- `portfolio.enter` refuses a candidate without a stop below price, so every entry carries a
  catastrophe stop at `price * (1 - stop_fraction)`; the portfolio watches it
  (is_stop_resting = False). Monthly rotation drives every other exit
- `Portfolio._prepare` backtests daily-only selections through `get_historical_prices` when
  every strategy is `Daily`. Extend that test so a BAA-only backtest takes the same path
- `is_taken`, `is_capped` and one position per symbol still apply; a symbol already held by
  another strategy blocks the BAA entry — record a warning event
- size through the existing `portfolio.enter`; the notional cap makes the picks near equal
  weight
- keep the regime and picks between iterations; recompute once per month
- record an info event each rebalance naming the regime and the picks
- add a `# allocation` section to `spec.strategies.md` in the same `py:surface` style
