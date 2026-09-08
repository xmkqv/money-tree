# ts pglite

[ts](../code/ts.md)
[catalog](../../catalogs/pgsql.md)
[PGlite documentation](https://pglite.dev/docs)

- create the database with `PGlite.create()` so readiness and extension types are established
- use parameterized queries for external values
- use IndexedDB for browser persistence
- dump and restore persisted data before a PGlite minor-version upgrade
- use an in-memory database only when persistence is not part of the contract

```ts
import { PGlite } from "@electric-sql/pglite";
import { live } from "@electric-sql/pglite/live";

const database = await PGlite.create("idb://library", {
  extensions: { live },
});

const result = await database.query<{ id: number; title: string }>(
  "select id, title from book where id = $1",
  [bookId],
);
```

## concurrency

- treat one PGlite instance as one exclusive connection behind a global mutex
- use the multi-tab worker with leader election when several tabs share one database
- expect a leader change to reset live-query state
- keep transactions flat; use raw SQL savepoints only when nested recovery is explicit

## durability

- a relaxed flush runs after each query and is never awaited, so one can outlive `close()`
- a relaxed IndexedDB flush can fail with `ErrnoError` 44 when a query unlinks a file mid-flush, and the next flush repairs it
- an `IdbFs` subclass passed as `fs` can fence flushes at close
- a durable flush fault at close must still close the filesystem, or the IndexedDB connection stays open and `deleteDatabase` blocks
- a relaxed flush fault surfaces as an unhandled rejection; the application decides which errno values are transient

```ts
import { IdbFs, PGlite } from "@electric-sql/pglite";

class LibraryFs extends IdbFs {
  #closing = false;
  #inflight: Promise<void> = Promise.resolve();

  override syncToFs(): Promise<void> {
    if (this.#closing) return Promise.resolve();
    this.#inflight = super.syncToFs();
    return this.#inflight;
  }

  override async closeFs(): Promise<void> {
    this.#closing = true;
    await this.#inflight.catch(() => undefined);
    try {
      await super.syncToFs();
    } finally {
      await super.closeFs();
    }
  }
}

const database = await PGlite.create({
  fs: new LibraryFs("library"),
  relaxedDurability: true,
});
```

## live queries

### apis

- use `live.query()` for small result sets and narrow rows
- use `live.incrementalQuery()` for large or wide result sets
- use `live.changes()` only when the application owns change application

### query text

- name every source table in the query text so refresh triggers can observe it
- add an inert CTE that names base tables when a PL/pgSQL function hides those reads
- alias joined columns explicitly

### lifecycle

- create a new live query when parameters change
- group related writes in one transaction to coalesce refresh work
- own one subscription per consumer under 0.5.4 because shared unsubscribe can stop every subscriber

## vite

```ts
import { defineConfig } from "vite";

export default defineConfig({
  optimizeDeps: { exclude: ["@electric-sql/pglite"] },
  worker: { format: "es" },
});
```

- allow SQL source paths explicitly when raw SQL globs read outside the package root
- permit `wasm-unsafe-eval` in the content security policy when PGlite runs in the browser

## schema

- replay the server migration history instead of copying a hand-maintained client schema
- track applied migration versions because PGlite has no first-party migration runner
- load an extension before `create extension`; create its target schema first when required
- do not require pgTAP because it is not included
- use PGlite Sync for rows only; create the local schema before synchronization
- use one shape per table and avoid join-dependent row security in shape filters

## source state

window: 2026-07-02 through 2026-09-06

- 2026-07-02: [`@electric-sql/pglite@0.5.4`](https://www.npmjs.com/package/@electric-sql/pglite/v/0.5.4) entered the stable package channel
- 2026-08-26: [`@electric-sql/pglite@0.5.8`](https://www.npmjs.com/package/@electric-sql/pglite/v/0.5.8) became the latest stable release
- 2026-09-06: the [benchmarks](https://pglite.dev/benchmarks) measured an IndexedDB small-row insert at 21.0 ms durable against 0.085 ms relaxed
- 2026-09-06: the [filesystems reference](https://pglite.dev/docs/filesystems) recorded IndexedDB as the browser default and OPFS as unsupported on Safari
- 2026-09-06: `0.5.8` `close()` scheduled one more relaxed flush through the terminate and freed the module without draining it
- 2026-09-06: `0.5.8` relaxed flushes on IDBFS rejected with errno 44 mid-session with no close in progress
