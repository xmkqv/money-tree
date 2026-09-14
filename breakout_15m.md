# breakout_15m

A third breakout variant. Everything below is derived from how `breakout_5m`
and `breakout_10m` already differ.

## The insight

The two existing variants differ along one line: a longer opening range is a
slower, rarer, higher-conviction setup, so it gets asked for more proof and
paid more per trade.

```
opening range     5 ──────────► 10 ──────────► 15
volume proof    1.3 ──────────► 1.5 ──────────► 1.7
targets     1.5/2.5/4 ──► 2/3/5 ──────────► 2.5/3.5/6
chase limit    none ──────────► 0.25 ────────► 0.20
risk/trade    0.15% ──────────► 0.50% ───────► 0.25%
```

Two things step up with range length: the proof demanded and the reward
targeted. One steps down: how far you will chase.

## The rules

Everything not listed comes from the shared `BREAKOUT__*` block. Same stop
placement, same 3-position family cap, same scale-out, same flatten 6 minutes
before the close.

**Opening range 15 minutes.** The range is set 09:30–09:45. Entry looks happen
at 09:45, 10:00, 10:15 and 10:30 — four chances, against twelve for the 5m.

**Volume multiple 1.7.** Continues the +0.2 per five minutes of range. By 09:45
a real move has had time to show its volume, so a 1.5 bar is no longer unusual.

**Targets 2.5 / 3.5 / 6.0 R.** A 15-minute range produces a wider stop, so the
trade has to run further to be worth the slot. Continues the +0.5 / +0.5 / +1.0
step from 5m to 10m.

**Chase limit 0.20, not 0.25.** This number is a fraction of the range, and the
range grows with time. Holding the fraction flat would let you chase a bigger
and bigger dollar distance.

```
5m range  |--|         0.25 x range = small chase
10m range |------|     0.25 x range = medium chase
15m range |----------| 0.25 x range = large chase  <- shrink the fraction
```

**Risk 0.25% per trade, set explicitly.** `breakout_10m` leaves this at `none`,
which inherits the global 0.5% — 3.3x the 5m's risk. That is a gap left by not
choosing, not a graded step. 0.25% sits between the two.

**Paused on arrival.** Backtest before it competes for slots.

## Two problems to settle before it runs

### 1. The family cap is 3 and the 5m fires first

```
09:35 ── 5m takes slot 1
09:40 ── 5m takes slot 2
09:45 ── 15m arrives ── 1 slot left, maybe zero
```

`cap_keys()` returns the whole `breakout` family, so every variant shares
`BREAKOUT__POSITIONS_MAX = 3`. The earlier strategy always wins. A 15m strategy
running beside a live 5m strategy will almost never trade.

Pick one: raise the family cap, run 15m with 5m paused, or make the cap a
per-variant setting.

### 2. Two shared settings are counted in bars, so they silently loosen

| Setting | On 5m | On 15m |
|---|---|---|
| `SIGNAL_BARS_MAX = 2` | break must be under 10 min old | break can be 30 min old |
| `TRAIL_ATR_MULTIPLE = 1.5` | 1.5 x a small ATR | 1.5 x a much larger ATR |

The freshness rule triples in length and the trailing stop gives back much more
of the move. Neither is what "same settings" implies.

### Also expect the screening to invert

`RANGE_FRACTION_MIN = 0.004` rejects narrow ranges, and 15-minute ranges are
rarely narrow, so it stops screening. `STOP_FRACTION_MAX = 0.05` rejects wide
stops, and 15-minute ranges produce wide stops, so it starts rejecting a lot.
The 15m will be cut mostly by the stop-width ceiling, not the range floor.

## The edits

Six places.

### 1. `src/mt/config/values.py` line 14

Add the key. Order here is the registry order.

```python
type StrategyKey = Literal["breakout_5m", "breakout_10m", "breakout_15m", "daily_sma", "daily_tfb"]
```

### 2. `src/mt/config/settings.py` line 45

Add the section under the other two breakouts.

```python
    breakout_5m: BreakoutVariationSection
    breakout_10m: BreakoutVariationSection
    breakout_15m: BreakoutVariationSection
```

### 3. `src/mt/strategies/breakout.py`, at the bottom

Add after `Breakout10m`.

```python
class Breakout15m(Breakout):
    key = "breakout_15m"
    code = "f"
```

### 4. `src/mt/strategies/registry.py`

Import it and register it. The tuple order must match `STRATEGY_KEYS` exactly.

```python
from .breakout import Breakout5m, Breakout10m, Breakout15m
```

```python
STRATEGIES: tuple[type[Strategy], ...] = (Breakout5m, Breakout10m, Breakout15m, DailySma, DailyTfb)
```

### 5. `mise.toml`, a new block after `## breakout_10m`

```ini
## breakout_15m
BREAKOUT_15M__OPENING_MINUTES = "15"
BREAKOUT_15M__VOLUME_MULTIPLE = "1.7"
BREAKOUT_15M__TARGET_MULTIPLES = "[2.5, 3.5, 6.0]"
BREAKOUT_15M__ENTRY_EXTENSION_MAX = "0.20"
BREAKOUT_15M__EQUITY_RISK_FRACTION_MAX = "0.0025"
BREAKOUT_15M__IS_PAUSED = "true"
```

### 6. `mise.toml` line 14

Add it to the running set. It is paused, so it will not trade until you flip
`IS_PAUSED`.

```ini
STRATEGIES = "breakout_5m,daily_sma,daily_tfb,breakout_10m,breakout_15m"
```

## Check it loads

```
mise run test
```

Three things fail loudly if a step is missed: a missing settings field, a tuple
order that does not match `STRATEGY_KEYS`, and a duplicate `code` letter. `f` is
free. `o`, `m`, `s` and `t` are taken.

## Optional: split the two bar-counted settings

Only needed if the settings from problem 2 should differ per variant. In
`src/mt/config/sections.py`, move them out of `BreakoutSection`:

```python
class BreakoutVariationSection(StrategySection):
    opening_minutes: Count
    volume_multiple: Amount
    target_multiples: tuple[float, float, float]
    entry_extension_max: OptionalFraction
    signal_bars_max: Count
    trail_atr_multiple: Amount
```

Then every variant needs its own `BREAKOUT_5M__SIGNAL_BARS_MAX`,
`BREAKOUT_10M__…` and so on, and the two reads in `breakout.py` change:

```python
settings.breakout.signal_bars_max   ->  self.signal_bars_max
settings.breakout.trail_atr_multiple -> self.trail_atr_multiple
```
