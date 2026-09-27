# [drizzle][drizzle-orm:docs]

## constrained sqlite table

```ts
import { sql, eq } from "drizzle-orm"
import { sqliteTable, integer, text, unique, check } from "drizzle-orm/sqlite-core"
record = sqliteTable("record", {
    id: integer("id").primaryKey({ autoIncrement: true }),
    label: text("label").notNull(),
}, table => [
    unique("record_label_unique").on(table.label),
    check("record_label_nonempty", sql`length(${table.label}) > 0`),
])
type Row = typeof record.$inferSelect
type Insert = typeof record.$inferInsert
```

## bun sqlite connection

```ts
import { Database } from "bun:sqlite"
import { drizzle } from "drizzle-orm/bun-sqlite"
client = new Database(filename)
client.run("PRAGMA foreign_keys = ON")
db = drizzle(client, { schema })
```

## projection

```ts
rows = db.select({ id: record.id, label: record.label })
    .from(record).where(eq(record.id, id)).all()
```

## returned mutations

```ts
inserted = db.insert(record).values(input).returning().get()
updated = db.update(record).set({ label }).where(eq(record.id, id)).returning().all()
deleted = db.delete(record).where(eq(record.id, id)).returning({ id: record.id }).all()
```

## atomic writes

```ts
db.transaction(tx => {
    row = tx.insert(record).values(input).returning().get()
    tx.insert(dependent).values({ recordId: row.id, value }).run()
    return row
})
```

## prepared lookup

```ts
lookup = db.select().from(record)
    .where(eq(record.id, sql.placeholder("id"))).prepare()
row = lookup.get({ id })
```

## interpolated sql

```ts
rows = db.select().from(record)
    .where(sql`lower(${record.label}) like lower(${pattern})`).all()
```

## refs

[drizzle-orm:docs]: https://orm.drizzle.team/docs/overview

[drizzle-orm:bun-sqlite]: https://orm.drizzle.team/docs/connect-bun-sqlite
    we mirror most popular SQLite-like `all`, `get`, `values` and `run`

[drizzle-orm:schema]: https://orm.drizzle.team/docs/sql-schema-declaration
