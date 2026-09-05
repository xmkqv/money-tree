# py polars

[py](../code/py.md)
[research catalog](../../catalogs/polars.md)

- use `polars>=1.43,<2`
- a pipeline remains lazy until a named materialization boundary
- a native expression replaces a python row function

## query plans

### lazy source

```py
import polars as pl


orders = (
    pl.scan_parquet("orders/**/*.parquet")
    .filter(pl.col("status") == "paid")
    .select("customer_id", "ordered_on", "gross", "fee")
)
```

### optimized plan

```py
plan = orders.explain(engine="streaming")
```

### streaming physical plan

```py
graph = orders.show_graph(
    show=False,
    raw_output=True,
    engine="streaming",
    plan_stage="physical",
)
```

### streaming materialization

```py
paid_orders = orders.collect(engine="streaming")
```

### lazy sink

```py
orders.sink_parquet("paid-orders.parquet")
```

### schema-known pivot

- a lazy-frame pivot is unstable

```py
monthly_revenue = orders.pivot(
    "month",
    on_columns=["jan", "feb", "mar"],
    index="customer_id",
    values="net",
    aggregate_function="sum",
)
```

## schemas

### complete input schema

```py
import polars as pl


ORDER_SCHEMA = pl.Schema(
    {
        "order_id": pl.UInt64,
        "customer_id": pl.UInt64,
        "ordered_on": pl.String,
        "status": pl.String,
        "gross": pl.Decimal(precision=12, scale=2),
        "fee": pl.Decimal(precision=12, scale=2),
    }
)

orders = pl.scan_csv("orders.csv", schema=ORDER_SCHEMA)
```

### partial input override

```py
orders = pl.scan_csv(
    "orders.csv",
    schema_overrides={
        "order_id": pl.UInt64,
        "customer_id": pl.UInt64,
        "gross": pl.Decimal(precision=12, scale=2),
        "fee": pl.Decimal(precision=12, scale=2),
    },
)
```

### explicit temporal parser

```py
orders = orders.with_columns(
    ordered_on=pl.col("ordered_on").str.to_date("%Y-%m-%d", strict=True),
)
```

### finite category

```py
ORDER_STATUS = pl.Enum(["pending", "paid", "refunded"])

orders = orders.with_columns(
    status=pl.col("status").cast(ORDER_STATUS, strict=True),
)
```

## expressions

### named expression

```py
net = (pl.col("gross") - pl.col("fee")).alias("net")
orders = orders.with_columns(net)
```

### dependent expressions

```py
orders = (
    orders
    .with_columns(net=pl.col("gross") - pl.col("fee"))
    .with_columns(margin=pl.col("net") / pl.col("gross"))
)
```

### filtered projection

```py
paid_orders = orders.filter(
    (pl.col("status") == "paid") & pl.col("gross").is_not_null()
).select(
    "order_id",
    "customer_id",
    "ordered_on",
    "net",
)
```

### grouped aggregation

```py
customer_summary = orders.group_by("customer_id").agg(
    order_count=pl.len(),
    revenue=pl.col("net").sum(),
    latest_order=pl.col("ordered_on").max(),
)
```

### window aggregation

```py
orders = orders.with_columns(
    customer_share=(
        pl.col("net") / pl.col("net").sum().over("customer_id")
    ),
)
```

### native nested transform

```py
orders = orders.with_columns(
    tags=pl.col("tags").list.eval(pl.element().str.to_lowercase()),
)
```

## relationships

### declared join cardinality

```py
orders = orders.join(
    customers,
    on="customer_id",
    how="left",
    validate="m:1",
)
```

### existence join

```py
paid_customers = customers.join(
    paid_orders.select("customer_id").unique(),
    on="customer_id",
    how="semi",
)
```

### sorted proximity join

```py
priced_trades = trades.sort("symbol", "at").join_asof(
    quotes.sort("symbol", "at"),
    on="at",
    by="symbol",
    strategy="backward",
    tolerance="5m",
)
```

### explicit output order

```py
customer_summary = customer_summary.sort(
    "revenue",
    "customer_id",
    descending=[True, False],
    nulls_last=True,
)
```

## missingness

### typed null replacement

```py
MONEY = pl.Decimal(precision=12, scale=2)

orders = orders.with_columns(
    fee=pl.col("fee").fill_null(pl.lit(0, dtype=MONEY)),
)
```

### nan normalization

```py
metrics = metrics.with_columns(
    ratio=pl.col("ratio").fill_nan(None),
)
```

### null-aware branch

```py
orders = orders.with_columns(
    size=(
        pl.when(pl.col("gross").is_null())
        .then(None)
        .when(pl.col("gross") >= 100)
        .then(pl.lit("large"))
        .otherwise(pl.lit("standard"))
    ),
)
```

## verification

### exact frame contract

```py
from polars.testing import assert_frame_equal


assert_frame_equal(actual, expected, check_exact=True)
```

### tolerant numeric contract

```py
assert_frame_equal(
    actual,
    expected,
    rel_tol=1e-9,
    abs_tol=1e-12,
)
```

### schema contract

```py
from polars.testing import assert_schema_equal


assert_schema_equal(orders.collect_schema(), EXPECTED_SCHEMA)
```

### strict vertical union

```py
orders = pl.concat([january_orders, february_orders], how="vertical")
```
