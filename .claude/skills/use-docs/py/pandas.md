# [pandas][pandas:docs]

2.3.3 · pandas-stubs 3.0 · Python 3.12+ syntax

```py
import numpy as np
import pandas as pd
from pandas import DataFrame, DatetimeIndex, Series, Timedelta, Timestamp

ZONE = "America/New_York"
```

[`DatetimeIndex.tz_localize(tz)` / `tz_convert(tz)`][pandas:tz] → `DatetimeIndex`; `DataFrame.index` is typed `Index[Any]`, so narrow it once.

```py
def to_zone(frame: DataFrame, zone: str = ZONE) -> DataFrame:
    stamps = DatetimeIndex(frame.index)  # typed narrowing; ints coerce silently, strings raise
    if stamps.tz is None:
        stamps = stamps.tz_localize("UTC")  # attach a zone; never moves the instant
    return frame.set_axis(stamps.tz_convert(zone)).sort_index()  # convert; same instants


frame = to_zone(frame)
stamps = DatetimeIndex(frame.index)
sessions = stamps.normalize()  # local midnight per row, tz kept
days, clocks = stamps.date, stamps.time  # object arrays of date / time
same_day = frame.loc[sessions == sessions[-1]]
frame.index.has_duplicates, frame.index.is_monotonic_increasing
```

[`between_time` / `at_time` / label `.loc` slices][pandas:between-time] → `DataFrame`; time-of-day filters follow the index zone.

```py
regular = frame.between_time("09:30", "16:00", inclusive="left")  # daily repeat, half-open
opening = frame.between_time("09:30", "09:35", inclusive="left")
noon = frame.at_time("12:00")
window = frame.loc[Timestamp("2026-03-02 09:35", tz=ZONE) :]  # slice ends are inclusive
after = frame[DatetimeIndex(frame.index) > Timestamp(cutoff)]  # wrap datetimes; index > datetime fails strict
recent = frame["close"].tail(20)
```

[`resample(rule, closed, label, origin, offset)`][pandas:resample] → `Resampler`; `.agg` with a dict folds OHLCV bars.

```py
ohlcv = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
hourly = (
    regular.resample("1h", offset="30min")  # bins start 09:30, 10:30, ...
    .agg(ohlcv)
    .dropna(subset=["open"])  # empty bins (gaps, overnight) come back as NaN rows
)
daily = regular.resample("1D").agg(ohlcv).dropna(subset=["open"])
bands = regular["close"].resample("30min").ohlc()  # columns: open, high, low, close
month_end = daily["close"].resample("ME").last()  # calendar bins; origin is ignored
```

[`groupby(key)` / `pd.Grouper(freq=)` with named aggregation][pandas:groupby] → per-session reductions keyed by local date.

```py
day = DatetimeIndex(regular.index).normalize()
per_day = regular.groupby(day).agg(
    high=("high", "max"),
    low=("low", "min"),
    first=("open", "first"),
    volume=("volume", "sum"),
)
last_close = regular["close"].groupby(day).last()
gap = (regular["close"].groupby(day).first() / last_close.shift(1) - 1).dropna()
running = regular["volume"].groupby(day).cumsum()  # per-day cumulative, same index as input
weekly = regular["volume"].groupby(pd.Grouper(freq="W")).sum()
```

[`rolling` / `ewm` / `shift` / `diff` / `clip` / `where`][pandas:window] → `Series` built from whole-column expressions, no row loops.

```py
close, high = frame["close"], frame["high"]
average = close.rolling(20).mean()  # int window: min_periods defaults to the window
recent_high = high.rolling("30min").max()  # offset window on a DatetimeIndex
smoothed = close.ewm(alpha=1 / 14, adjust=False).mean()  # Wilder smoothing
change = close.pct_change()
gain = close.diff().clip(lower=0)
peak = close.cummax()
drawdown = close / peak - 1
signal = (close > average) & (average > average.shift(3)) & (close > high.shift(1))
is_active = bool(signal.iloc[-1])  # last row of a boolean Series
masked = close.where(signal)  # NaN where False; mask() inverts
```

[`idxmax` / `argmax` / `loc[mask]`][pandas:idxmax] → first hit of a boolean condition as label or position.

```py
above = close > high.iloc[:5].max()
below = close < frame["low"].iloc[:5].min()
hit = above | below
if hit.any():
    label = hit.idxmax()  # index label of the first True
    position = int(hit.argmax())  # integer position of the first True
    direction = 1 if above.loc[label] else -1
    first_hit = close.loc[hit].index[0]  # equivalent, label only
    price = close.iloc[[position]].item()  # one-element Series -> Python scalar
```

[`MultiIndex` `xs` / `droplevel` / `get_level_values`][pandas:multiindex] → per-key frames from a stacked response; `concat(keys=)` stacks them.

```py
stacked = pd.concat({"AAA": frame, "BBB": frame}, names=["symbol", "time"])
by_key = {
    key: group.droplevel("symbol")  # back to a plain DatetimeIndex
    for key, group in stacked.groupby(level="symbol")
}
one = stacked.xs("AAA", level="symbol")
keys = stacked.index.get_level_values("symbol").unique()
latest = stacked.groupby(level="symbol")["close"].last()
rows = frame.head(3).to_dict(orient="index")  # {timestamp: {column: value}}
for row in frame.head(3).itertuples():  # namedtuples; faster than iterrows
    row.Index, row.close
```

[`asof` / `reindex` / `merge_asof`][pandas:merge-asof] → align a series to arbitrary instants without loops.

```py
cutoff = Timestamp("2026-03-03 12:00", tz=ZONE)
price = frame["close"].asof(cutoff)  # last non-NaN value at or before cutoff
label = daily.index.asof(cutoff)  # last index label at or before cutoff
prior = last_close.shift(1).reindex(per_day.index)  # align by label; missing -> NaN
targets = pd.DataFrame({"at": pd.to_datetime([cutoff])}).sort_values("at")
joined = pd.merge_asof(
    targets,
    frame[["close"]],
    left_on="at",
    right_index=True,
    direction="backward",
    tolerance=Timedelta("5min"),  # farther matches become NaN
)
```

[`Timestamp` / `Timedelta` / `DateOffset` / `date_range`][pandas:offsets] → calendar arithmetic; typed, copy-safe pipelines.

```py
start = Timestamp("2026-03-31", tz=ZONE)
prior_month = start - pd.DateOffset(months=1)  # 2026-02-28, clamps to month end
two_sessions = start - pd.offsets.BDay(2)  # weekdays only; no holiday calendar
window_end = start.floor("D") + Timedelta(hours=16)
grid = pd.date_range("2026-03-02", "2026-03-06", freq="B", tz=ZONE)

# pandas-stubs: return concrete generics instead of cast()
def daily_move(closes: Series[float]) -> Series[float]:
    return closes.pct_change().dropna()


def tidy(frame: DataFrame) -> DataFrame:
    return (
        frame.pipe(to_zone)
        .assign(typical=lambda x: (x["high"] + x["low"] + x["close"]) / 3)
        .loc[lambda x: x["volume"] > 0]  # callable selectors keep the chain free of temps
    )
```

## refs

[pandas:docs]: https://pandas.pydata.org/pandas-docs/version/2.3.3/index.html

[pandas:tz]: https://pandas.pydata.org/pandas-docs/version/2.3.3/reference/api/pandas.DatetimeIndex.tz_localize.html
    It does not move the time to another time zone.
    TypeError: If the Datetime Array/Index is tz-aware and tz is not None.
    'raise' - raises AmbiguousTimeError (default)

[pandas:between-time]: https://pandas.pydata.org/pandas-docs/version/2.3.3/reference/api/pandas.DataFrame.between_time.html
    Include boundaries; whether to set each bound as closed or open.
    TypeError: If the index is not a DatetimeIndex

[pandas:resample]: https://pandas.pydata.org/pandas-docs/version/2.3.3/reference/api/pandas.DataFrame.resample.html
    The timezone of origin must match the timezone of the index.
    'start_day': origin is the first day at midnight of the timeseries

[pandas:groupby]: https://pandas.pydata.org/pandas-docs/version/2.3.3/reference/api/pandas.Grouper.html

[pandas:window]: https://pandas.pydata.org/pandas-docs/version/2.3.3/reference/api/pandas.DataFrame.rolling.html
    For a window that is specified by an offset, `min_periods` will default to 1.

[pandas:idxmax]: https://pandas.pydata.org/pandas-docs/version/2.3.3/reference/api/pandas.Series.idxmax.html

[pandas:multiindex]: https://pandas.pydata.org/pandas-docs/version/2.3.3/user_guide/advanced.html

[pandas:merge-asof]: https://pandas.pydata.org/pandas-docs/version/2.3.3/reference/api/pandas.merge_asof.html
    Both DataFrames must be sorted by the key.

[pandas:offsets]: https://pandas.pydata.org/pandas-docs/version/2.3.3/user_guide/timeseries.html

[pandas:cow]: https://pandas.pydata.org/pandas-docs/version/2.3.3/user_guide/copy_on_write.html
    Chained assignment will never work
    CoW will be enabled by default in version 3.0.

[pandas:stubs]: https://github.com/pandas-dev/pandas-stubs
