# add strategy: quality_gp (gross profitability)

Add a new strategy `quality_gp` to the bot. Follow the path `daily_20sma` takes through the
code (`rules/values.py`, `rules/sections.py`, `rules/settings.py`, `strategies/`,
`strategies/registry.py`, `mise.toml`, `spec.strategies.md`). Read `spec.md` and
`spec.strategies.md` first. Do not write tests. Run `mise run test` at the end.

## source

- Novy-Marx (2013), "The Other Side of Value: The Gross Profitability Premium", Journal of
  Financial Economics
- Chen & Welch — profitability is the anomaly family that held up after 2005

## rule

```
universe
    the portfolio universe (common stocks, price and turnover filters), already ranked by
    turnover; keep the first universe_size (1000)
    drop financials (SIC 6000–6999)
    drop any stock without both fundamentals below

signal
    gross profitability = (revenue - cost of revenue) / total assets
    revenue and cost of revenue: trailing four quarters, else the last fiscal year
    total assets: latest balance sheet
    fundamentals older than fundamentals_max_age_days → drop

selection
    rank by gross profitability, descending
    picks = the top holdings_max names
    keep a holding while it ranks inside keep_rank (buffer; cuts turnover)

rebalance
    first session of each month, entry_minutes after the open
    exit holdings outside keep_rank (reason "signal"), then fill free slots from picks
    equal weight; long only
```

The paper's top decile of 1000 is 100 names. The book holds 20 positions in total, so the
sleeve holds the top `holdings_max` names.

## data: SEC EDGAR (free)

Add `src/mt/data/edgar.py` beside `finnhub.py`, using the same `http.py` client, timeout
section and caching style.

- XBRL frames give one concept for every filer in one call:
  `https://data.sec.gov/api/xbrl/frames/us-gaap/{concept}/USD/{period}.json`
  (duration periods like `CY2025Q2`, instant periods like `CY2025Q2I`)
- concepts: `GrossProfit`; else `Revenues` or
  `RevenueFromContractWithCustomerExcludingAssessedTax` minus `CostOfRevenue` or
  `CostOfGoodsAndServicesSold`; `Assets` (instant)
- CIK → ticker: `https://www.sec.gov/files/company_tickers.json`
- SIC code: `https://data.sec.gov/submissions/CIK##########.json` (`sic` field), cached
- SEC requires a `User-Agent` header with a contact; add `EDGAR__USER_AGENT` as a setting and
  a secret in `mise.production.toml` / `mise.development.toml` like the Finnhub key
- SEC allows 10 requests per second; stay under it
- fetch once per month on the rebalance day; cache the ranked table in memory

## identity

- key `quality_gp` → family `quality`, variation `GP`
- order code `q` (unused; existing codes are o, m, f, s, t, w)
- `holdings_max = 6`

## settings (`QUALITY_GP__*` and `EDGAR__*` in mise.toml)

```
QUALITY_GP__UNIVERSE_SIZE = "1000"
QUALITY_GP__KEEP_RANK = "20"
QUALITY_GP__FUNDAMENTALS_MAX_AGE_DAYS = "200"
QUALITY_GP__ENTRY_MINUTES = "15"
QUALITY_GP__STOP_FRACTION = "0.25"
QUALITY_GP__DOES_HEED_EARNINGS = "false"
QUALITY_GP__HOLDINGS_MAX = "6"
QUALITY_GP__IS_PAUSED = "false"

EDGAR__TIMEOUT__CONNECT_SECONDS = "2.0"
EDGAR__TIMEOUT__READ_SECONDS = "30.0"
EDGAR__TIMEOUT__WRITE_SECONDS = "5.0"
EDGAR__TIMEOUT__POOL_SECONDS = "5.0"
```

Add `quality_gp` to `STRATEGIES`.

## fit with the existing code

- `portfolio.assets()` is the ranked universe; take the first `universe_size`
- `portfolio.enter` refuses a candidate without a stop below price, so every entry carries a
  catastrophe stop at `price * (1 - stop_fraction)`; the portfolio watches it
  (is_stop_resting = False). Monthly rotation drives every other exit
- size through the existing `portfolio.enter`; the notional cap makes the picks near equal
  weight
- `Portfolio._prepare` backtests daily-only selections through `get_historical_prices` when
  every strategy is `Daily`. Extend that test so a quality-only backtest takes the same path.
  Backtests must read fundamentals as filed on the backtest date (frames carry `filed`);
  never use later filings
- record an info event each rebalance with the picks and their gross profitability
- record a warning when EDGAR fails and skip the rebalance; retry next iteration
- add a `# quality` section to `spec.strategies.md` in the same `py:surface` style
