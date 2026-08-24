# py-datasci

- arrays and native expressions carry bulk computation
- schemas, axes, order, missingness, and warm-up rows are explicit
- lazy plans delay materialization until the smallest useful result is selected

## libs

### numpy

- use dense arrays, broadcasting, ufuncs, and generalized contractions

```py
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view


returns = np.diff(prices, axis=0) / prices[:-1]
windows = sliding_window_view(returns, window_shape=20, axis=0)
means = windows.mean(axis=-1, keepdims=True)
centered = windows - means
covariance = np.einsum(
    "taw,tbw->tab",
    centered,
    centered,
    optimize=True,
) / (windows.shape[-1] - 1)
```

### pandas

- use labeled alignment, grouped windows, and ordered joins

```py
import pandas as pd


assert bars.index.is_unique
bars = bars.sort_values("at")
rolling = bars.groupby("symbol", sort=False)["close"].rolling(
    20,
    min_periods=20,
)
bars["sma_20"] = rolling.mean().droplevel("symbol")

features = pd.merge_asof(
    bars,
    quotes.sort_values("at"),
    on="at",
    by="symbol",
    direction="backward",
    tolerance=pd.Timedelta("2s"),
)
```

### polars

- use lazy scans and native expressions for parallel query execution

```py
import polars as pl


features = (
    pl.scan_parquet("bars/**/*.parquet")
    .sort("symbol", "at")
    .with_columns(
        close_return=pl.col("close").pct_change().over("symbol"),
        sma_20=pl.col("close").rolling_mean(20).over("symbol"),
        volume_z=(
            (
                pl.col("volume")
                - pl.col("volume").rolling_mean(20)
            )
            / pl.col("volume").rolling_std(20)
        ).over("symbol"),
    )
    .filter(pl.col("sma_20").is_not_null())
    .select("symbol", "at", "close_return", "sma_20", "volume_z")
)

feature_frame = features.collect()
```

### pyarrow

- use typed columnar scans for projection, filtering, and zero-copy interchange

```py
import pyarrow.dataset as ds


dataset = ds.dataset(
    "bars",
    format="parquet",
    partitioning="hive",
)
scanner = dataset.scanner(
    columns={
        "symbol": ds.field("symbol"),
        "at": ds.field("at"),
        "notional": ds.field("close") * ds.field("volume"),
    },
    filter=(ds.field("at") >= start) & ds.field("symbol").isin(symbols),
    batch_size=65_536,
    use_threads=True,
)
notional_by_symbol = scanner.to_table().group_by("symbol").aggregate(
    [("notional", "sum")],
)
```

### duckdb

- use vectorized SQL for larger-than-memory files and analytical windows

```py
import duckdb


features = duckdb.sql(
    """
    select
        symbol,
        "at",
        close,
        avg(close) over recent as sma_20,
        stddev_samp(close) over recent as volatility_20,
        count(*) over recent as observations
    from read_parquet('bars/**/*.parquet')
    window recent as (
        partition by symbol
        order by "at"
        rows between 19 preceding and current row
    )
    qualify observations = 20
    """
).arrow()
```

### scipy

- use axis-aware algorithms for batched statistics and uncertainty estimates

```py
import numpy as np
from scipy import stats


bootstrap = stats.bootstrap(
    (strategy_returns,),
    np.mean,
    axis=0,
    vectorized=True,
    n_resamples=20_000,
    batch=512,
    method="BCa",
    rng=np.random.default_rng(7),
)
mean_return_low = bootstrap.confidence_interval.low
mean_return_high = bootstrap.confidence_interval.high
```

### scikit-learn

- use composite estimators to keep preprocessing inside time-aware validation

```py
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import TimeSeriesSplit, cross_validate
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


features = ColumnTransformer(
    [
        (
            "numeric",
            make_pipeline(SimpleImputer(strategy="median"), StandardScaler()),
            numeric_columns,
        ),
        (
            "category",
            OneHotEncoder(
                handle_unknown="infrequent_if_exist",
                min_frequency=50,
            ),
            category_columns,
        ),
    ],
)
model = make_pipeline(features, LogisticRegression(max_iter=2_000))
splitter = TimeSeriesSplit(n_splits=5, test_size=250, gap=20)
scores = cross_validate(
    model,
    samples,
    targets,
    cv=splitter,
    scoring={
        "roc_auc": "roc_auc",
        "log_loss": "neg_log_loss",
    },
    n_jobs=-1,
)
```

### numba

- use generalized ufuncs for recursive kernels across independent batches

```py
from numba import float64, guvectorize


@guvectorize(
    [(float64[:], float64[:])],
    "(n)->(n)",
    nopython=True,
    target="parallel",
)
def drawdown(equity, out):
    peak = equity[0]
    for index in range(equity.shape[0]):
        peak = max(peak, equity[index])
        out[index] = equity[index] / peak - 1.0


scenario_drawdowns = drawdown(equity_paths)
```

### pandas-ta-classic

- use a strategy to compose indicators while preserving pandas columns

```py
import pandas_ta_classic as ta


strategy = ta.Strategy(
    name="trend-volatility",
    ta=[
        {"kind": "ema", "length": 20},
        {"kind": "ema", "length": 50},
        {"kind": "adx", "length": 14},
        {"kind": "atr", "length": 14},
        {"kind": "rsi", "length": 14},
    ],
)
source_columns = bars.columns.copy()
bars.ta.cores = 4
bars.ta.strategy(strategy)
indicator_columns = bars.columns[~bars.columns.isin(source_columns)]
indicators = bars.loc[:, indicator_columns]
```

### vectorbt

- use broadcast parameter combinations for signal and portfolio research

```py
import numpy as np
import vectorbt as vbt


fast, slow = vbt.MA.run_combs(
    close,
    window=np.arange(5, 105, 5),
    r=2,
    short_names=["fast", "slow"],
)
entries = fast.ma_crossed_above(slow)
exits = fast.ma_crossed_below(slow)
portfolios = vbt.Portfolio.from_signals(
    close,
    entries,
    exits,
    fees=0.0005,
    sl_stop=0.02,
    freq="1D",
)
ranking = portfolios.sharpe_ratio().sort_values(ascending=False)
```

## vectorized computations

- an axis contract names every dimension before broadcasting
- a native ufunc, expression, or estimator replaces element-wise python dispatch
- `numpy.vectorize` changes call shape but does not compile the wrapped function
- masks define invalid arithmetic, missing values, and warm-up rows explicitly
- lazy projection and predicate pushdown precede materialization
- recursive state uses a scan or compiled kernel instead of false broadcasting

### axis contract

```py
import numpy as np


assert returns.ndim == 2
time_count, asset_count = returns.shape
thresholds = np.linspace(0.0025, 0.03, num=12)

signal_cube = returns[:, :, None] >= thresholds[None, None, :]
assert signal_cube.shape == (time_count, asset_count, thresholds.size)
```

### normalized broadcast

```py
raw_weights = np.where(signal_cube, 1.0, 0.0)
gross = raw_weights.sum(axis=1, keepdims=True)
weights = np.zeros_like(raw_weights)
np.divide(raw_weights, gross, out=weights, where=gross != 0)
```

### masked arithmetic

```py
strategy_returns = np.full_like(pnl, np.nan, dtype=np.float64)
np.divide(
    pnl,
    capital,
    out=strategy_returns,
    where=capital != 0,
)
```

### bounded parameter batches

```py
for threshold_batch in np.array_split(thresholds, 4):
    signals = returns[:, :, None] >= threshold_batch
    batch_scores = score_signals(signals, returns)
    score_sink.write(threshold_batch, batch_scores)
```

# py-datasci research

- window: 2026-02-24 through 2026-08-24
- gate: the upstream repository has activity inside the window
- last active: the repository `pushed_at` date from GitHub on 2026-08-24
- evidence: current official documentation and upstream repositories
- docs indexes: Context7 and Mintlify

## recent libs

| link                                                                | last active |  stars | developer experience                                           | feature tags                                     |
|---------------------------------------------------------------------|-------------|-------:|----------------------------------------------------------------|--------------------------------------------------|
| [NumPy](https://github.com/numpy/numpy)                             | 2026-08-23  | 32,591 | the base dense-array and ufunc layer                           | arrays, broadcasting, ufuncs, linear algebra     |
| [pandas](https://github.com/pandas-dev/pandas)                      | 2026-08-24  | 49,557 | the default labeled in-memory table API                        | frames, groups, windows, joins                   |
| [Polars](https://github.com/pola-rs/polars)                         | 2026-08-24  | 39,465 | an expression-first lazy dataframe engine                      | lazy, parallel, streaming, arrow                 |
| [Apache Arrow](https://github.com/apache/arrow)                     | 2026-08-24  | 17,045 | typed interchange and dataset scans without dataframe coupling | columnar, parquet, datasets, interchange         |
| [DuckDB](https://github.com/duckdb/duckdb)                          | 2026-08-24  | 40,557 | analytical SQL directly over files and dataframes              | sql, parquet, windows, out-of-core               |
| [SciPy](https://github.com/scipy/scipy)                             | 2026-08-24  | 14,950 | axis-aware numerical algorithms over NumPy arrays              | statistics, optimize, signal, sparse             |
| [scikit-learn](https://github.com/scikit-learn/scikit-learn)        | 2026-08-24  | 67,043 | composable preprocessing, models, and validation               | ml, pipelines, validation, metrics               |
| [Numba](https://github.com/numba/numba)                             | 2026-08-21  | 11,126 | compiled kernels for recurrences that resist array algebra     | jit, gufunc, parallel, cuda                      |
| [pandas-ta-classic](https://github.com/xgboosted/pandas-ta-classic) | 2026-07-25  |    421 | a maintained pandas strategy and indicator extension           | finance, indicators, strategies, multiprocessing |
| [vectorbt](https://github.com/polakowo/vectorbt)                    | 2026-08-02  |  8,803 | broadcast signal and portfolio research over parameter grids   | finance, signals, backtesting, numba             |

## docs search log

[1] Dense vectorization starts with shapes, broadcasting, ufuncs, and contractions.

- NumPy applies compiled element-wise operations across broadcast-compatible axes.
- Sliding window views expose rolling blocks without copying their source array.
- `einsum` expresses batched reductions without materializing repeated operands.

Refs: [broadcasting](https://numpy.org/doc/2.4/user/basics.broadcasting.html),
  [sliding windows](https://numpy.org/doc/2.4/reference/generated/numpy.lib.stride_tricks.sliding_window_view.html),
  [`einsum`](https://numpy.org/doc/2.4/reference/generated/numpy.einsum.html)

[2] Labeled time series need explicit grouped windows and ordered joins.

- pandas grouped rolling operations retain source labels after one index level is removed.
- `merge_asof` matches sorted observations by time, group, direction, and tolerance.

Refs: [grouped rolling](https://pandas.pydata.org/docs/reference/api/pandas.api.typing.SeriesGroupBy.rolling.html),
  [`merge_asof`](https://pandas.pydata.org/docs/reference/api/pandas.merge_asof.html)

[3] Expression engines optimize whole query plans rather than isolated operations.

- Polars keeps scans lazy and resolves window expressions through native query nodes.
- DuckDB evaluates analytical windows directly over Parquet scans.
- Arrow dataset scanners push column selection and filters into fragmented data sources.

Refs: [Polars lazy API](https://docs.pola.rs/user-guide/concepts/lazy-api/),
  [DuckDB window functions](https://duckdb.org/docs/stable/sql/functions/window_functions.html),
  [Arrow datasets](https://arrow.apache.org/docs/python/dataset.html)

[4] Axis-aware algorithms preserve compiled execution above the array layer.

- SciPy passes an axis to vectorized statistics and batches bootstrap resamples.
- scikit-learn composes column transforms and models inside time-series validation.
- Numba generalized ufuncs compile a core recurrence across independent dimensions.

Refs: [SciPy bootstrap](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html),
  [scikit-learn composition](https://scikit-learn.org/stable/modules/compose.html),
  [Numba gufuncs](https://numba.readthedocs.io/en/stable/user/vectorize.html)

[5] Current finance tooling separates indicator composition from portfolio simulation.

- pandas-ta-classic executes named indicator strategies and returns aligned columns.
- Its core control selects serial execution or multiprocessing for a whole strategy.
- vectorbt broadcasts indicator combinations into signal and portfolio dimensions.
- Stale public pandas-ta sources are excluded in favor of pandas-ta-classic.

Refs: [pandas-ta-classic strategies](https://xgboosted.github.io/pandas-ta-classic/strategies.html),
  [pandas-ta-classic signals](https://xgboosted.github.io/pandas-ta-classic/performance.html),
  [vectorbt indicators](https://vectorbt.dev/api/indicators/factory/),
  [vectorbt portfolios](https://vectorbt.dev/api/portfolio/base/)
