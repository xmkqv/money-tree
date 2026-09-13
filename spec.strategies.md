---
name: strategies
elide:
  - frame shaping and indicator arithmetic
---

- a strategy owns its signals and its holding management
- a frozen code attributes every order to its strategy
- family is the key before the underscore; variation is the rest
- a variation declares every field of its own settings section
- a missing declaration fails at import, not at runtime

```py:surface
strategy
    key, code, family, variation, holdings_max, is_paused, is_stop_resting

    entry_window(opens, closes) → (start, end)
    begin(day)
    run(session)
        candidates → portfolio.enter
    manage(holding, session)
        exits → portfolio.exit; stops → portfolio.protect
    ladder(holding, quantity) → ladder | none
```

# breakout

Variations: breakout_5m, breakout_10m. One opening range, one volume test.

```py:surface
entry
    range = the opening high and low over opening_minutes
    marks = low, mid_fraction, high
    range width / price < range_fraction_min → skip
    stop distance / price outside the stop_fraction bounds → skip
    volume to the signal close < volume_multiple * historical mean → skip
    window = range close → min(session close, open + scan_minutes)
    signal = the first close outside the range, within signal_bars_max
    entry beyond entry_extension_max of the range, when set → skip
    family cap reached → skip
    enter at the next open
    stop = long_stop_fraction or short_stop_fraction of the range above its low

management
    targets = target_multiples of the initial stop distance
    each target → close its share of target_fractions; the last → close the rest
    partial short exits round down to whole shares; zero → skip
    the first target → stop at entry; then trail by trail_atr_multiple
    trailing requires trail_bars_min
    close_lead_minutes before the session close → close the rest
```

# daily

Variations: daily_sma, daily_tfb. One trend test, one session per entry.

```py:surface
signals
    daily_sma = price > SMA(trend_sessions) > SMA(trend_sessions_long)
        and RSI ≥ rsi_min and ADX ≥ adx_min
        and close crosses above SMA(average_sessions) and close[-1] > close[-2]
    daily_tfb = turnover over turnover_sessions
        and price > SMA(trend_sessions) rising over trend_lag_sessions
        and ADX ≥ adx_min and close > the previous high

entry
    benchmark close ≤ SMA(average_sessions) → skip
    heeded earnings within earnings.block_days → skip
    strategy cap reached → skip
    one entry per asset per session, between the open and the close
    enter at the next open, else the next permitted iteration
    stop = entry - stop_atr_multiple * ATR

management
    stop = max(stop, highest close since entry - stop_atr_multiple * ATR)
    close < stop or close < SMA(average_sessions) or RSI < exit_rsi_max
        → exit at the next open
    heeded earnings → exit at the open of the last session before the event
    retry an earnings exit until it is submitted
```
