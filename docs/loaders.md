# Loaders

Research checked on 2026-07-28

## Shape-compliant options

### Decision

Use [dlt 1.29](https://pypi.org/project/dlt/) for reproducible batch and micro-batch ingestion

Land immutable raw data as Parquet and load query-ready tables into DuckDB

Keep WebSocket capture outside dlt and hand completed micro-batches back to dlt

This split gives one loader contract without pretending an ELT library is a tick recorder

### Fit

| Need | dlt fit | Treatment |
| --- | --- | --- |
| Paginated REST history | Strong | Use the declarative REST source |
| Incremental REST polling | Strong | Persist cursors and merge keys |
| Bulk CSV, JSONL, or Parquet | Strong | Use the filesystem source |
| SQL snapshots or CDC | Strong | Use the SQL source or replication source |
| SDK iterators | Strong | Wrap them as resources |
| WebSocket ticks | Partial | Capture first and yield bounded batches |
| Order-book reconstruction | Weak | Use a dedicated sequenced event log |
| Feature engineering | Wrong layer | Run after raw ingestion |

[Core sources](https://dlthub.com/docs/dlt-ecosystem/verified-sources) cover REST, files, and SQL

### Source patterns

#### Declarative REST

Use the [REST API source](https://dlthub.com/docs/dlt-ecosystem/verified-sources/rest_api)
for endpoint trees that share authentication and pagination

Configure these fields per endpoint

- Primary key and merge disposition
- Cursor path and initial value
- Pagination strategy
- Rate-limit backoff
- Response data selector
- Parent-child endpoint binding
- Request timeout and retry budget

Prefer server timestamps over local receipt timestamps for cursors

Retain a small overlap window and deduplicate after every incremental pull

#### Python resource

Use a custom resource for SDKs, signed requests, archives, and unusual pagination

Yield bounded Arrow tables or lists rather than one object at a time

Keep authentication and provider translation inside the provider adapter

Keep dlt hints beside the resource so schema and write behavior remain reviewable

#### Live capture bridge

Write WebSocket messages to an append-only local spool before normalization

Rotate by byte size and time rather than by row count alone

Record sequence number, exchange time, receipt time, channel, and connection id

Close a batch atomically and let dlt ingest only closed batches

Never make dlt pipeline state the sole record of an exchange sequence

### Alternatives

| Option | Strength | Why it is not the default |
| --- | --- | --- |
| Direct Polars and httpx | Small and fast | Rebuilds state, retries, schema, and lineage |
| Airbyte | Large connector catalog | Service footprint is high for this workspace |
| Singer taps | Interchangeable connectors | Quality and state semantics vary by tap |
| Dagster | Strong asset orchestration | Complements ingestion rather than replacing it |
| Prefect | Flexible workflow runtime | Complements ingestion rather than replacing it |
| Kafka or Redpanda | Durable live streams | Operational cost is unjustified before scale |

### Recommendation

Adopt dlt now for historical and polled inputs

Use DuckDB plus Parquet until data volume or concurrency proves it insufficient

Add a durable stream service only after local spooling fails measured requirements

## Other

### Recommended layout

```text
provider
  -> capture
  -> dlt resource
  -> raw Parquet
  -> normalized DuckDB tables
  -> point-in-time transforms
  -> Torch datasets
```

Use one pipeline name per provider, account, environment, and data class

Use one raw table per provider endpoint or event schema

Retain provider payloads before applying a common market schema

#### Local default

| Layer | Default | Reason |
| --- | --- | --- |
| Raw store | Partitioned Parquet | Cheap replay and portable columnar reads |
| Catalog | DuckDB | Local SQL, Parquet scans, and no service dependency |
| Loader | dlt | State, retries, schema history, and incremental loading |
| Batch frame | Arrow or Polars | Low-copy handoff into analytics |
| Orchestration | Plain process first | Avoid a scheduler before jobs need one |

The [DuckDB destination](https://dlthub.com/docs/dlt-ecosystem/destinations/duckdb)
supports Parquet, JSONL, and direct connection objects

### Canonical fields

Every loaded observation should retain these provenance fields where available

| Field | Meaning |
| --- | --- |
| `provider` | Stable provider key |
| `dataset` | Endpoint, feed, or archive key |
| `instrument_id` | Internal point-in-time instrument key |
| `provider_symbol` | Exact upstream symbol |
| `venue` | Listing or execution venue |
| `event_time` | Upstream event time in UTC |
| `available_time` | Earliest time the value was knowable |
| `received_time` | Local receipt time in UTC |
| `sequence` | Upstream sequence or update id |
| `revision` | Provider revision or vintage |
| `ingested_at` | Loader timestamp in UTC |
| `payload_hash` | Stable raw-payload fingerprint |

`available_time` is mandatory for macro, fundamentals, news, and revised data

Do not derive it from period end or filing coverage dates

### State and write rules

| Data behavior | Write disposition | Key |
| --- | --- | --- |
| Immutable trades | Append | Venue plus trade id |
| Mutable bars | Merge | Instrument plus interval plus open time |
| Fundamentals | Append revisions | Entity plus fact plus period plus filing |
| Macro vintages | Append revisions | Series plus observation date plus vintage |
| Reference data | Type-2 history | Provider id plus effective interval |
| News | Append then enrich | Provider article id |
| Full snapshots | Replace staging only | Snapshot id |

Use [schema contracts](https://dlthub.com/docs/general-usage/schema-contracts)
after discovery to stop silent type drift

Allow new nullable fields in raw tables

Require review for removed fields, incompatible types, and key changes

Keep dlt system tables because they provide load and schema lineage

### Performance

dlt can parallelize extract, normalize, and load stages

The [performance guide](https://dlthub.com/docs/reference/performance) documents
threaded extraction, process normalization, file rotation, and threaded loads

Use these controls in this order

1. Yield larger Arrow or Polars batches
2. Rotate files to expose load parallelism
3. Parallelize independent endpoints
4. Increase normalize workers for nested JSON
5. Increase load workers only when the destination can absorb them
6. Benchmark Parquet against the destination-native default

Do not run the same pipeline name and working directory concurrently

DuckDB serializes some multi-file Parquet loads into one table

Prefer direct Parquet scans when repeated DuckDB ingestion adds no value

### Reliability controls

- Set explicit connect, read, and total timeouts
- Bound retry time and respect `Retry-After`
- Persist response metadata for quota and cache diagnosis
- Quarantine malformed records rather than dropping them
- Alert on empty successful loads
- Compare expected and observed time coverage
- Reconcile source counts where the provider exposes them
- Check clock skew before live capture
- Encrypt credentials outside pipeline state
- Test restart from every pipeline stage

Schema evolution is automatic by default

Review the [schema evolution behavior](https://dlthub.com/docs/general-usage/schema-evolution)
before accepting upstream changes in curated tables

### Integration boundary

The money-tree `Source` should read a committed dataset snapshot

It should not perform a remote backfill during a prediction call

The loader owns acquisition, provenance, normalization, and committed snapshots

The predictor owns feature windows and model-specific tensors

Expose snapshot identity through observation metadata before enabling live trading

### Adoption gates

1. Load one daily REST source into Parquet and DuckDB
2. Prove idempotent restart with an overlapping cursor
3. Reproduce a snapshot from raw files alone
4. Detect a deliberately injected schema break
5. Benchmark Arrow batches against row dictionaries
6. Capture and replay one WebSocket channel through the spool bridge
7. Add retention and credential handling before unattended operation
