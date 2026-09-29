# [pandas-ta-classic][pandas-ta-classic:docs]

0.8.32 · import name `pandas_ta_classic` · Python 3.10+ · pandas Series/DataFrame in, Series/DataFrame/None out

```py
import pandas as pd
import pandas_ta_classic as ta
from pandas_ta_classic.utils import above, below, cross, cross_value, verify_series
```

[`ta.rsi(close, length=14, drift=1, talib=False)`][pandas-ta-classic:momentum] → `Series | None`; every direct call returns `None` when the input is too short.

```py
def require[T: (pd.Series, pd.DataFrame)](result: T | None, what: str) -> T:
    if result is None:  # input shorter than length, or not a Series
        raise ValueError(f"{what}: not enough rows")
    return result


close, high, low = frame["close"], frame["high"], frame["low"]
rsi = require(ta.rsi(close, length=14), "rsi")  # Series named "RSI_14"
sma = require(ta.sma(close, length=20), "sma")  # "SMA_20"; rolling mean, min_periods=length
ema = require(ta.ema(close, length=20), "ema")  # "EMA_20"; SMA-seeded, adjust=False
```

[`ta.adx(high, low, close, length=14, lensig=None, mamode="rma")`][pandas-ta-classic:trend] → `DataFrame | None` with three named columns.

```py
adx = require(ta.adx(high, low, close, length=14), "adx")
list(adx.columns)  # ["ADX_14", "DMP_14", "DMN_14"]
strength: pd.Series = adx["ADX_14"]  # lensig defaults to length, so it names the ADX column
trending = (strength >= 25) & (adx["DMP_14"] > adx["DMN_14"])
# NaN head: DMP/DMN = length, ADX = 2 * length - 1 (14 -> 14 and 27 leading NaN)
```

[`ta.atr(high, low, close, length=14, mamode="rma", percent=False)`][pandas-ta-classic:volatility] → `Series | None`; the column letter after `ATR` is the first letter of `mamode`.

```py
atr = require(ta.atr(high, low, close, length=14), "atr")  # "ATRr_14" (rma)
atr_sma = require(ta.atr(high, low, close, length=14, mamode="sma"), "atr")  # "ATRs_14"
atr_pct = require(ta.atr(high, low, close, length=14, percent=True), "atr")  # "ATRr_14p"
stop_distance = 1.5 * atr.iloc[-1]  # NaN when the frame is barely longer than length
```

[`ta.donchian(high, low, lower_length=20, upper_length=20)`][pandas-ta-classic:volatility] → `DataFrame` of rolling low, mid and high; [`ta.true_range`][pandas-ta-classic:volatility], [`ta.percent_return`][pandas-ta-classic:performance] and [`ta.pvol`][pandas-ta-classic:volume] cover ranges, returns and price times volume.

```py
channel = require(ta.donchian(high, low, lower_length=20, upper_length=20), "donchian")
list(channel.columns)  # ["DCL_20_20", "DCM_20_20", "DCU_20_20"]
prior_high = channel["DCU_20_20"].shift(1)  # exclude the current bar from its own breakout level
breakout = close > prior_high

tr = require(ta.true_range(high, low, close), "true_range")  # first row NaN, needs a previous close
ret = require(ta.percent_return(close, length=1), "return")  # "PCTRET_1" = close / close.shift(1) - 1
log_ret = require(ta.log_return(close), "log_return")  # "LOGRET_1"
traded = require(ta.pvol(close, frame["volume"]), "pvol")  # "PVOL" = close * volume
avg_traded = traded.rolling(20).mean()
```

[`above` / `below` / `cross` / `cross_value`][pandas-ta-classic:utils] → boolean or int Series; `asint=False` keeps `bool` for masks.

```py
crossed_up = cross(close, sma, above=True, asint=False)  # strict: close > sma now, close < sma before
crossed_down = cross(close, sma, above=False, asint=False)
is_over = above(close, sma, asint=False)  # inclusive: close >= sma
is_under = below(close, sma, asint=False)  # inclusive: close <= sma
rsi_up = cross_value(rsi, 50, above=True, asint=False)  # crosses a scalar level
crossed_up.name  # "close_XA_SMA_20"; XB for crossings down, A / B for levels
entry = bool(crossed_up.iloc[-1] and rsi.iloc[-1] >= 50)
```

[`df.ta.<indicator>(append=True)`][pandas-ta-classic:accessor] → the result, and the columns are also written into `df` in place.

```py
bars = frame.copy()  # append=True mutates the caller's frame
bars.ta.sma(length=50, append=True)  # adds "SMA_50"
bars.ta.adx(length=14, append=True)  # adds "ADX_14", "DMP_14", "DMN_14"
bars.ta.sma(close="volume", length=20, prefix="VOL", append=True)  # adds "VOL_SMA_20"
bars.ta.rsi(length=14, col_names=("RSI",), append=True)  # explicit output name
bars.ta.ohlc4(append=True)  # price average column "OHLC4"
# the accessor reads lowercase "open", "high", "low", "close", "volume" columns;
# pass other names as close="Adj", high="H", ... or hand Series to the direct functions
```

[`ta.Strategy(name, ta=[{"kind": ...}])`][pandas-ta-classic:strategies] → a named batch that `df.ta.strategy(...)` runs and appends.

```py
study = ta.Strategy(
    name="core",
    ta=[
        {"kind": "sma", "length": 20},
        {"kind": "sma", "length": 50},
        {"kind": "sma", "close": "volume", "length": 20, "prefix": "VOL"},
        {"kind": "rsi", "length": 14},
        {"kind": "atr", "length": 14},
        {"kind": "adx", "length": 14},
    ],
)


def enrich(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out.ta.cores = 0  # 0 runs in-process; the default uses every CPU core as a worker pool
    out.ta.strategy(study)  # returns None; columns are appended to out
    return out


if __name__ == "__main__":  # required when workers are spawned (cores > 0)
    enriched = enrich(frame)
```

[`fillna`, `fill_method`, `offset`][pandas-ta-classic:dataframe-api] → keyword conventions shared by every indicator; warm-up NaN stays unless filled.

```py
def latest(series: pd.Series) -> float | None:
    value = series.iloc[-1] if len(series) else float("nan")
    return None if pd.isna(value) else float(value)


shifted = require(ta.sma(close, 20, offset=1), "sma")  # offset=1 shifts the result forward one row
ffilled = require(ta.rsi(close, 14, fill_method="ffill"), "rsi")  # ffill / bfill only
zeroed = require(ta.rsi(close, 14, fillna=0), "rsi")  # replaces warm-up NaN with 0; usually wrong
ready = bars.dropna(subset=["SMA_50", "ADX_14"])  # drop warm-up rows before signals
signal_rsi = require(ta.rsi(close, 14, signal_indicators=True, xa=70, xb=30), "rsi")
list(signal_rsi.columns)  # ["RSI_14", "RSI_14_A_70", "RSI_14_B_30"]
```

## refs

[pandas-ta-classic:docs]: https://xgboosted.github.io/pandas-ta-classic/

[pandas-ta-classic:momentum]: https://github.com/xgboosted/pandas-ta-classic/blob/main/pandas_ta_classic/momentum/rsi.py
    drift (int): The difference period. Default: 1

[pandas-ta-classic:trend]: https://github.com/xgboosted/pandas-ta-classic/blob/main/pandas_ta_classic/trend/adx.py
    lensig (int): Signal Length. Like TradingView's default ADX. Default: length
    mamode (str): See ```help(ta.ma)```. Default: 'rma'

[pandas-ta-classic:volatility]: https://github.com/xgboosted/pandas-ta-classic/blob/main/pandas_ta_classic/volatility/atr.py
    percent (bool, optional): Return as percentage. Default: False

[pandas-ta-classic:performance]: https://github.com/xgboosted/pandas-ta-classic/blob/main/pandas_ta_classic/performance/percent_return.py

[pandas-ta-classic:volume]: https://github.com/xgboosted/pandas-ta-classic/blob/main/pandas_ta_classic/volume/pvol.py

[pandas-ta-classic:utils]: https://github.com/xgboosted/pandas-ta-classic/blob/main/pandas_ta_classic/utils/_core.py
    Anything else -- a list, a numpy array, a DataFrame -- is a caller error.

[pandas-ta-classic:accessor]: https://xgboosted.github.io/pandas-ta-classic/dataframe_api.html
    # Set the number of cores to use for strategy multiprocessing

[pandas-ta-classic:strategies]: https://xgboosted.github.io/pandas-ta-classic/strategies.html
    Keyword arguments passed to `strategy()` reach every indicator in the run.
    # For no multiprocessing, set this value to 0.

[pandas-ta-classic:dataframe-api]: https://github.com/xgboosted/pandas-ta-classic/blob/main/docs/dataframe_api.md
    df.ta.donchian(lower_length=10, upper_length=15, append=True)

[pandas-ta-classic:pypi]: https://pypi.org/project/pandas-ta-classic/
