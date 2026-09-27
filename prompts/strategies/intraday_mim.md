# add strategy: intraday_mim (Market Intraday Momentum)

Add a new strategy `intraday_mim` to the bot. Follow the path `daily_20sma` takes through the
code (`rules/values.py`, `rules/sections.py`, `rules/settings.py`, `strategies/`,
`strategies/registry.py`, `mise.toml`, `spec.strategies.md`). Read `spec.md` and
`spec.strategies.md` first. Do not write tests. Run `mise run test` at the end.

## source

- Gao, Han, Li & Zhou (2018), "Market Intraday Momentum", Journal of Financial Economics
- Zarattini, Aziz & Barbon (2024), "Beat the Market: An Effective Intraday Momentum Strategy
  for S&P500 ETF (SPY)" — adds the noise band filter

## rule

```
signal
    first = SPY return from the prior session close to open + 30 minutes
    band = mean of |first| over the last noise_sessions sessions
    |first| < noise_multiple * band → no trade today

entry
    at entry_minutes_before_close before the close (default 30 → 15:30 ET)
    first > 0 → buy long_symbol (SPY)
    first < 0 → buy short_symbol (SH, the -1x S&P 500 ETF)
    one entry per session

stop
    long: entry * (1 - stop_band_multiple * band)
    stop rests at the broker (is_stop_resting = True, like breakout)

exit
    close_lead_minutes before the close → close the rest (reason "close")
    no overnight holding
```

Gao et al. measure the last half hour (15:30–16:00). The entry time is a setting so 15:00
can be tested.

## identity

- key `intraday_mim` → family `intraday`, variation `MIM`
- order code `i` (unused; existing codes are o, m, f, s, t, w)
- `holdings_max = 1`

## settings (`INTRADAY_MIM__*` in mise.toml)

```
INTRADAY_MIM__LONG_SYMBOL = "SPY"
INTRADAY_MIM__SHORT_SYMBOL = "SH"
INTRADAY_MIM__FIRST_MINUTES = "30"
INTRADAY_MIM__ENTRY_MINUTES_BEFORE_CLOSE = "30"
INTRADAY_MIM__CLOSE_LEAD_MINUTES = "2"
INTRADAY_MIM__NOISE_SESSIONS = "14"
INTRADAY_MIM__NOISE_MULTIPLE = "1.0"
INTRADAY_MIM__STOP_BAND_MULTIPLE = "1.0"
INTRADAY_MIM__LOOKBACK_DAYS = "30"
INTRADAY_MIM__HOLDINGS_MAX = "1"
INTRADAY_MIM__IS_PAUSED = "false"
```

Add `intraday_mim` to `STRATEGIES`.

## fit with the existing code

- `Portfolio._universe` keeps common stocks only, so SPY and SH never reach the strategy.
  Add a way for a strategy to declare fixed symbols (for example a classmethod
  `symbols() -> tuple[str, ...]`, empty by default) and have `Portfolio._prepare` add them to
  `requested` and to the assets the strategy sees. BAA and the quality sleeve reuse this.
- the prior close comes from `portfolio.daily_frame` for SPY (SPY is also the benchmark)
- the first-30-minute price and the band history come from `portfolio.minute_frames` with
  `minutes = first_minutes`, over `lookback_days`
- `entry_window` returns (close - entry_minutes_before_close, close - close_lead_minutes)
- `manage` closes the holding at close - close_lead_minutes; the stop order handles the rest
- size through the existing `portfolio.enter` (risk per trade over the stop distance, capped by
  `RISK__NOTIONAL_USD_MAX`)
- record an info event when the noise filter skips a day, like `scan.emptied`
- add a `# intraday` section to `spec.strategies.md` in the same `py:surface` style
