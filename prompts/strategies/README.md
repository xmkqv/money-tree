# strategy prompts

Paste one file at a time into Claude Code, in this order:

1. `intraday_mim.md` — Market Intraday Momentum on SPY (intraday, 30-minute bars)
2. `allocation_baa.md` — Bold Asset Allocation (monthly ETF rotation)
3. `quality_gp.md` — gross profitability quality sleeve (monthly stock picks, EDGAR data)

Each prompt stands alone. Each adds one strategy through the same path `daily_20sma` takes:
`rules/values.py` → `rules/sections.py` → `rules/settings.py` → `strategies/<file>.py` →
`strategies/registry.py` → `mise.toml` → `spec.strategies.md`.

## ensemble

- all three run beside the existing strategies; `STRATEGIES` in `mise.toml` selects them
- `RISK__POSITIONS_MAX` (20) is shared by the whole book; each sleeve's `HOLDINGS_MAX` splits it
- sleeve caps in these prompts: MIM 1, BAA 3, quality 6 → 10 slots, leaving 10 for breakout and daily
- the book holds one position per symbol, so MIM trades SPY and BAA uses the aggressive
  universe (no SPY); a symbol collision blocks the second strategy's entry
- `RISK__NOTIONAL_USD_MAX` (100) caps every position; short sales round to whole shares,
  so a SPY short never fills at that cap — MIM expresses down days through SH instead
