# polars

## lazy aggregation

```py
import polars as pl
summary = (
    pl.scan_parquet(source)
    .filter(pl.col("active"))
    .group_by("key")
    .agg(total=pl.col("value").sum(), count=pl.len())
    .sort("key")
)
summary.explain(engine="streaming")
summary.sink_parquet(destination)
```

## typed input

```py
schema = {"key": pl.String, "value": pl.Decimal(precision=12, scale=2)}
rows = pl.scan_csv(source, schema=schema)
```

## dependent expressions

```py
rows.with_columns(net=pl.col("gross") - pl.col("fee")).with_columns(
    share=pl.col("net") / pl.col("net").sum().over("key")
)
```

## validated join

```py
rows.join(lookup, on="key", how="left", validate="m:1")
rows.join(lookup.select("key"), on="key", how="semi")
```

## temporal proximity

```py
left.sort("key", "at").join_asof(
    right.sort("key", "at"), on="at", by="key", strategy="backward", tolerance="5m"
)
```

## nested expressions

```py
rows.with_columns(values=pl.col("values").list.eval(pl.element().str.to_lowercase()))
```

## typed missingness

```py
rows.with_columns(
    value=pl.col("value").fill_null(pl.lit(0, dtype=pl.Decimal(12, 2)))
)
```

## frame comparison

```py
from polars.testing import assert_frame_equal
assert_frame_equal(actual, expected, check_exact=True)
assert_frame_equal(actual, expected, rel_tol=1e-9, abs_tol=1e-12)
```

## tips

- lazy scans allow projection and predicate pushdown before materialization.
- null and nan have separate replacement operations.
- native expressions keep computation inside the query engine.
- [the api reference][api] documents expression and lazy-frame operations.

## refs

[api]: https://docs.pola.rs/api/python/stable/reference/index.html
