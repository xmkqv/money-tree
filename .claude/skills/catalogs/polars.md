# polars

- window: 2026-02-15 through 2026-08-15
- source policy: current primary documentation and project releases
- baseline: polars 1.43.2 stable

[polars package][polars-package]
    package data retrieved 2026-08-14
    python polars 1.43.2 was the latest stable release
    python polars 1.43.0 and 1.43.1 were yanked
    python 3.10 or newer is required

[polars 1432][polars-1432]
    release published 2026-08-01
    infer-schema-files was added to scan-csv
    categorical-to-integer casts were deprecated
    show-graph began requiring an explicit plan-stage
    ordering join slicing and nested-type interoperability received fixes

[polars 141][polars-141]
    release published 2026-05-22
    the streaming engine became stable
    lazy-frame gather and nested common-subplan elimination were added
    list-slice offsets and lengths gained scalar broadcasting
    string-cache was deprecated

[polars 142][polars-142]
    release published 2026-06-24
    direct string-to-temporal casts were deprecated
    cloud i/o gained byte-based concurrency control
    naive out-of-core spilling and external object-store support were added

[polars 143][polars-143]
    release published 2026-07-21
    lazy-frame profile numeric-to-categorical casts and unnamed list-to-struct calls were deprecated
    scan-arrow-c-stream exponentially weighted sums and partition-aware joins were added
    the exponentially weighted sums and join build-side option are unstable

[polars lazy][polars-lazy]
    documentation retrieved 2026-08-14
    lazy queries allow query optimization streaming and early schema checks
    scan functions expose source-level projection predicate and slice pushdown
    collect is the explicit materialization boundary

[polars optimizer][polars-optimizer]
    documentation retrieved 2026-08-14
    the optimizer performs predicate projection and slice pushdown
    the optimizer performs common-subplan elimination expression simplification and join ordering
    query plans remain inspectable with explain and show-graph

[polars streaming][polars-streaming]
    documentation retrieved 2026-08-14
    streaming execution is requested with collect engine streaming
    unsupported operations can fall back to the in-memory engine
    a physical streaming plan is inspected with an explicit engine and plan-stage

[polars schema][polars-schema]
    documentation retrieved 2026-08-14
    a frame schema defines ordered column names and data types
    lazy execution checks invalid operations before data processing
    a data-dependent schema requires an eager boundary or explicit output categories

[polars pivot][polars-pivot]
    documentation retrieved 2026-08-14
    lazy-frame pivot requires on-columns to declare its output categories
    lazy pivot preserves a static schema without an eager boundary
    lazy-frame pivot is unstable

[polars expressions][polars-expressions]
    documentation retrieved 2026-08-14
    expressions are composable lazy representations of transformations
    select with-columns filter and group-by provide distinct expression contexts
    a with-columns expression must preserve the input height

[polars rolling sum][polars-rolling-sum]
    documentation retrieved 2026-08-15
    a fixed rolling window includes its row and the preceding window-size-minus-one rows
    the default minimum sample count requires a complete window
    rolling-sum is the native expression for fixed-row moving sums

[polars categories][polars-categories]
    documentation retrieved 2026-08-14
    enum is preferred when the complete category set is known
    enum rejects values outside its declared category set
    categorical uses a shared global mapping by default

[polars missing][polars-missing]
    documentation retrieved 2026-08-14
    null represents missing data for every data type
    nan is a valid floating-point value and is distinct from null
    fill-null and fill-nan express separate policies

[polars udf][polars-udf]
    documentation retrieved 2026-08-14
    native expressions avoid per-value python call overhead
    plugins are preferred for custom expressions and data sources
    a user-defined function declares its return data type when practical

[polars joins][polars-joins]
    documentation retrieved 2026-08-14
    equi semi anti non-equi as-of and cross joins have distinct row semantics
    join keys may be expressions
    as-of joins match by key proximity

[polars testing][polars-testing]
    documentation retrieved 2026-08-14
    frame equality checks row order column order data types and values by default
    floating-point comparison supports explicit relative and absolute tolerances
    exact comparison is available when approximation is not part of the contract

[polars april][polars-april]
    article published 2026-04-16
    all major file formats gained streaming scans
    ndjson csv ipc delta and iceberg gained streaming source or sink coverage
    the streaming engine expanded across joins windows and aggregations

[polars 141 announcement][polars-141-announcement]
    article published 2026-05-26
    parquet metadata decoding became 1.61 to 3.29 times faster in the published footer benchmark
    nested common-subplan elimination removed repeated work at every nesting depth
    lazy-frame gather kept indexed row selection inside the lazy plan

[polars 143 announcement][polars-143-announcement]
    article published 2026-07-23
    list preserves nested list inputs while concat-list flattens them
    hive-partitioned joins can prune scans and distributed shuffles
    rolling min-by and max-by gained an amortized linear-time path

[polars kubernetes][polars-kubernetes]
    article published 2026-06-03
    the distributed engine became deployable on kubernetes
    existing lazy-frame queries can execute on remote clusters
    profiling and open-lineage events are available for remote queries

[polars cloud 09][polars-cloud-09]
    article published 2026-07-02
    select with-columns and filter expressions gained distributed lowering
    distributed unions of python scans and an iceberg sink were added
    manual on-premise scaling and disk i/o metrics were added

[cudf polars 2606][cudf-polars-2606]
    release published 2026-06-03
    cudf-polars gained ray mode for multi-gpu execution
    streaming execution options were unified across gpu runtimes
    partitioned execution can extend beyond one gpu or one node

## refs

[polars-package]: https://pypi.org/project/polars/
[polars-1432]: https://github.com/pola-rs/polars/releases/tag/py-1.43.2
[polars-141]: https://github.com/pola-rs/polars/releases/tag/py-1.41.0
[polars-142]: https://github.com/pola-rs/polars/releases/tag/py-1.42.0
[polars-143]: https://github.com/pola-rs/polars/releases/tag/py-1.43.0
[polars-lazy]: https://docs.pola.rs/user-guide/lazy/using/
[polars-optimizer]: https://docs.pola.rs/user-guide/lazy/optimizations/
[polars-streaming]: https://docs.pola.rs/user-guide/concepts/streaming/
[polars-schema]: https://docs.pola.rs/user-guide/lazy/schemas/
[polars-pivot]: https://docs.pola.rs/user-guide/transformations/pivot/
[polars-expressions]: https://docs.pola.rs/user-guide/concepts/expressions-and-contexts/
[polars-rolling-sum]: https://docs.pola.rs/api/python/stable/reference/expressions/api/polars.Expr.rolling_sum.html
[polars-categories]: https://docs.pola.rs/user-guide/expressions/categorical-data-and-enums/
[polars-missing]: https://docs.pola.rs/user-guide/expressions/missing-data/
[polars-udf]: https://docs.pola.rs/user-guide/expressions/user-defined-python-functions/
[polars-joins]: https://docs.pola.rs/user-guide/transformations/joins/
[polars-testing]: https://docs.pola.rs/api/python/stable/reference/api/polars.testing.assert_frame_equal.html
[polars-april]: https://pola.rs/posts/polars-in-aggregate-apr26/
[polars-141-announcement]: https://pola.rs/posts/polars-1-41/
[polars-143-announcement]: https://pola.rs/posts/polars-1-43/
[polars-kubernetes]: https://pola.rs/posts/polars-distributed-available-on-kubernetes/
[polars-cloud-09]: https://pola.rs/posts/polars-cloud-0-9/
[cudf-polars-2606]: https://github.com/rapidsai/cudf/releases/tag/v26.06.00
