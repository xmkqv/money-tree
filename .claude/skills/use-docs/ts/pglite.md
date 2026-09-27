# [pglite][@electric-sql/pglite:docs]

## persistent instance

```ts
import { PGlite } from "@electric-sql/pglite"
import { live } from "@electric-sql/pglite/live"
db = await PGlite.create("idb://example", { extensions: { live } })
```

## parameterized query

```ts
result = await db.query<{ id: number; value: string }>(
    "select id, value from record where id = $1", [id]
)
```

## transaction

```ts
await db.transaction(async tx => {
    await tx.query("update record set value = $1 where id = $2", [value, id])
    await tx.query("insert into event (record_id) values ($1)", [id])
})
```

## live result

```ts
subscription = await db.live.query(
    "select id, value from record order by id", [], result => render(result.rows)
)
onDispose(async () => await subscription.unsubscribe())
```

## incremental result

```ts
subscription = await db.live.incrementalQuery(
    "select id, value from record order by id", [], "id", result => render(result.rows)
)
onDispose(async () => await subscription.unsubscribe())
```

## refs

[@electric-sql/pglite:docs]: https://pglite.dev/docs/
    PGlite only has a single exclusive connection to the database

[@electric-sql/pglite:api]: https://pglite.dev/docs/api

[@electric-sql/pglite:live-queries]: https://pglite.dev/docs/live-queries
    refresh allows you to force a refresh of the query with the updated results
