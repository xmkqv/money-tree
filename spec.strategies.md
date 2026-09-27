---
name: strategies
reminders:
    - strategy spec is a faithful logical projection of the fundamental math
---

- family is the first segment of the key; variation is the rest
- a variation declares every field of its rules section; a missing field fails at import
- a cap counts holdings of the variation alone

# breakout

- variations: breakout_5m, breakout_10m, breakout_15m
- one opening range, one volume test
- the stop rests at the broker

```py:surface
entry
    range = the opening high and low over opening_minutes
    levels = low, mid_fraction, high
    range width / price < range_fraction_min → skip
    stop distance / price outside the stop_fraction bounds → skip
    volume to the signal close < volume_multiple * historical mean → skip
    window = range close → min(session close, open + scan_minutes)
    signal = the first close outside the range, within signal_bars_max
    entry beyond entry_extension_max of the range, when set → skip
    enter at the next open
    stop = low + {long_stop_fraction | short_stop_fraction} * range width

management
    targets = target_multiples of the initial stop distance
    each target closes its target_fractions share; the last closes the rest
    partial short exits round down to whole shares; zero → skip
    the first target → stop at entry; then trail by trail_atr_multiple after trail_bars_min
    close_lead_minutes before the session close → close the rest
```

# daily

- variations: daily_sma, daily_tfb, daily_20sma
- one trend test
- portfolio watches the stop

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
    one entry per asset per session, between the open and the close
    enter at the next open, else the next permitted iteration
    stop = entry - stop_atr_multiple * ATR

management
    stop = max(stop, highest close since entry - stop_atr_multiple * ATR)
    close < stop or close < SMA(average_sessions) or RSI < exit_rsi_max → exit at the next open
    heeded earnings → exit at the open of the last session before the event
    retry an earnings exit until it is submitted
```

## daily_20sma

- the trailing stop reads ATR over trail_hours bars
- the strategy reads market capitalization once per candidate per session

```py:surface
entry
    price > SMA(trend_sessions) > SMA(trend_sessions_long)
    rsi_min ≤ RSI ≤ rsi_max and ADX ≥ adx_min
    close crosses above SMA(average_sessions)
    market capitalization < market_cap_usd_min or unreadable → skip
    window = session open → open + entry_minutes
    stop = entry * (1 - stop_fraction)

management
    targets = entry * (1 + target_gains)
    each target closes its target_fractions share; the rest trails
    highest < entry * (1 + breakeven_gain) → the stop holds
    otherwise stop = max(stop, entry, highest - trail_atr_multiple * ATR)
    price ≤ stop → exit
    at the open, close < SMA(average_sessions) or RSI < exit_rsi_max → exit the rest
```

# intraday

- variations: intraday_mim
- Gao, Han, Li & Zhou (2018); noise band after Zarattini, Aziz & Barbon (2024)
- the stop rests at the broker

```py:surface
signal
    move = long_symbol first first_minutes bar close / prior session close - 1
    band = mean |move| over the prior noise_sessions sessions
    |move| < noise_multiple * band → skip the session

entry
    window = close - entry_minutes_before_close → close - close_lead_minutes
    move > 0 → buy long_symbol; move < 0 → buy short_symbol
    stop = entry * (1 - stop_band_multiple * band)

management
    close_lead_minutes before the session close → close the rest
```

# allocation

- variations: allocation_baa
- Keller (2022), Bold Asset Allocation
- closes are the last daily close of each month
- portfolio watches the stop

```py:surface
momentum
    fast = (12 * r1 + 4 * r3 + 2 * r6 + r12) / 4
    slow = p0 / mean(p0 … p12) - 1

selection, once per month
    canaries with fast < 0 ≥ breadth → defensive, else offensive
    offensive → top offensive_top offensive symbols by slow
    defensive → top defensive_top defensive symbols by slow;
        slow below the cash symbol → the cash symbol
    missing canary or cash closes → skip the month until readable

entry
    window = open + entry_minutes → close
    every pick not held → enter; stop = entry * (1 - stop_fraction)

management
    price ≤ stop → exit
    inside the window, a holding outside the picks → exit
```

# quality

- variations: quality_gp
- Novy-Marx (2013), gross profitability
- portfolio watches the stop

```py:surface
ranking, once per month
    universe = the first universe_size universe stocks
    score = gross profit / total assets, latest annual filing
    gross profit = GrossProfit, else revenue - cost of revenue
    filing older than fundamentals_max_age_days → skip
    industry ∈ excluded_industries → skip
    keep the top keep_rank
    no filing → skip
    unreadable filings or industries → retry after retry_minutes

entry
    window = open + entry_minutes → close
    the top holdings_max not held → enter; stop = entry * (1 - stop_fraction)

management
    price ≤ stop → exit
    inside the window, a holding outside keep_rank → exit
```
