# ts drizzle

[ts](../code/ts.md)
[catalog](../../catalogs/ts-orm.md)

- use stable `drizzle-orm@^0.45.2` and `drizzle-kit@^0.31.10`
- do not use a Drizzle ORM version below `0.45.2`; it has unsafe identifier and alias escaping
- use SQLite with Bun unless the task specifies another dialect or driver
- table, relation, and query builders are portable; `.all()`, `.get()`, `.run()`, and `.sync()` here are Bun SQLite operations
- defer all v1 APIs and migration guidance until Drizzle ORM and Drizzle Kit v1 are stable

## install

```sh
bun add drizzle-orm@^0.45.2
bun add --dev drizzle-kit@^0.31.10 @types/bun
```

## schema

- export every table and relation definition
- use singular table names and plural relation names
- give SQL columns explicit names; do not depend on a casing transform
- use database constraints for integrity and `relations()` for relational queries
- index foreign keys and columns used for filtering or ordering
- return an array from the table extra-configuration function
- infer row and insert types from the table

Example: `src/db/schema.ts`

```ts
import { relations, sql } from "drizzle-orm";
import {
  check,
  index,
  integer,
  sqliteTable,
  text,
  unique,
} from "drizzle-orm/sqlite-core";

export const user = sqliteTable(
  "user",
  {
    id: integer("id").primaryKey({ autoIncrement: true }),
    email: text("email").notNull(),
    name: text("name").notNull(),
    active: integer("active", { mode: "boolean" }).notNull().default(true),
    createdAt: integer("created_at", { mode: "timestamp" })
      .notNull()
      .default(sql`(unixepoch())`),
  },
  (table) => [
    unique("user_email_unique").on(table.email),
    check("user_name_check", sql`length(${table.name}) > 0`),
    index("user_created_at_index").on(table.createdAt),
  ],
);

export const post = sqliteTable(
  "post",
  {
    id: integer("id").primaryKey({ autoIncrement: true }),
    authorId: integer("author_id")
      .notNull()
      .references(() => user.id, { onDelete: "cascade" }),
    title: text("title").notNull(),
    createdAt: integer("created_at", { mode: "timestamp" })
      .notNull()
      .default(sql`(unixepoch())`),
  },
  (table) => [index("post_author_id_index").on(table.authorId)],
);

export const userRelations = relations(user, ({ many }) => ({
  posts: many(post),
}));

export const postRelations = relations(post, ({ one }) => ({
  author: one(user, {
    fields: [post.authorId],
    references: [user.id],
  }),
}));

export type User = typeof user.$inferSelect;
export type UserInsert = typeof user.$inferInsert;

export default { post, postRelations, user, userRelations };
```

## database

- pass the complete exported schema to `drizzle()`; relational queries need it
- fail when the database path is absent
- enable SQLite foreign-key enforcement for each connection

Example: `src/db/database.ts`

```ts
import { Database } from "bun:sqlite";
import { drizzle } from "drizzle-orm/bun-sqlite";
import schema from "./schema";

const databasePath = process.env.DB_FILE_NAME;
if (!databasePath) throw new Error("DB_FILE_NAME is unset");

const sqlite = new Database(databasePath);
sqlite.run("PRAGMA foreign_keys = ON");

export default drizzle(sqlite, { schema });
```

## selects

- select only the fields the caller needs
- express filters, joins, and ordering with schema columns and Drizzle operators
- finish Bun SQLite queries with the sync operation that matches the expected result

```ts
import { asc, eq } from "drizzle-orm";
import database from "./database";
import { user } from "./schema";

const users = database
  .select({ id: user.id, email: user.email, name: user.name })
  .from(user)
  .where(eq(user.active, true))
  .orderBy(asc(user.name))
  .all();
```

## relational queries

- stable `relations()` is application metadata; it does not create foreign keys
- define both directions that callers need
- call `.sync()` on a Bun SQLite relational query

```ts
import database from "./database";

const users = database.query.user.findMany({
  where: (user, { eq }) => eq(user.active, true),
  with: {
    posts: {
      orderBy: (post, { desc }) => [desc(post.createdAt)],
    },
  },
}).sync();
```

## mutations

- include a predicate in each update and delete unless the task explicitly targets every row
- use `returning()` when later work needs the stored values
- check the affected row count or returned row and fail on an unexpected result

```ts
import { eq } from "drizzle-orm";
import database from "./database";
import { post, user, type UserInsert } from "./schema";

const userInsert: UserInsert = {
  email: "ada@example.com",
  name: "Ada",
};

const insertedUser = database.insert(user).values(userInsert).returning().get();
if (!insertedUser) throw new Error("InsertUser returned no row");

const updatedUsers = database
  .update(user)
  .set({ active: false })
  .where(eq(user.id, insertedUser.id))
  .returning({ id: user.id })
  .all();
if (updatedUsers.length !== 1) {
  throw new Error("UpdateUser changed an unexpected row count");
}

const deletedPosts = database
  .delete(post)
  .where(eq(post.authorId, insertedUser.id))
  .returning({ id: post.id })
  .all();
```

## transactions

- use a synchronous transaction callback with `bun:sqlite`
- keep every dependent write in the same transaction
- throw to roll back when an invariant fails

```ts
import database from "./database";
import { post, user } from "./schema";

export default (email: string, title: string) =>
  database.transaction((transaction) => {
    const author = transaction
      .insert(user)
      .values({ email, name: email })
      .returning()
      .get();
    if (!author) throw new Error("InsertUser returned no row");

    const insertedPost = transaction
      .insert(post)
      .values({ authorId: author.id, title })
      .returning()
      .get();
    if (!insertedPost) throw new Error("InsertPost returned no row");

    return insertedPost;
  });
```

## prepared queries

- prepare queries that run repeatedly with the same shape
- use placeholders for values, not for SQL structure

```ts
import { eq, sql } from "drizzle-orm";
import database from "./database";
import { user } from "./schema";

const findUserById = database
  .select()
  .from(user)
  .where(eq(user.id, sql.placeholder("userId")))
  .prepare();

const selectedUser = findUserById.get({ userId: 1 });
if (!selectedUser) throw new Error("FindUser returned no row");
```

## sql

- interpolate values, tables, columns, and SQL fragments through the `sql` template
- never put runtime input in `sql.raw()`
- map runtime choices to known schema columns; do not let input select an identifier or alias
- `sql.identifier()` and `.as()` require `drizzle-orm@0.45.2` or later and still require an allowlist for structural choices

```ts
import { asc, sql } from "drizzle-orm";
import database from "./database";
import { user } from "./schema";

const userOrder = {
  createdAt: user.createdAt,
  name: user.name,
} as const;

type UserOrder = keyof typeof userOrder;

export default (order: UserOrder, query: string) =>
  database
    .select({ id: user.id, name: user.name })
    .from(user)
    .where(sql`lower(${user.name}) like lower(${`%${query}%`})`)
    .orderBy(asc(userOrder[order]))
    .all();
```

## migrations

Example: `drizzle.config.ts`

```ts
import { defineConfig } from "drizzle-kit";

const databasePath = process.env.DB_FILE_NAME;
if (!databasePath) throw new Error("DB_FILE_NAME is unset");

export default defineConfig({
  dialect: "sqlite",
  schema: "./src/db/schema.ts",
  out: "./drizzle",
  dbCredentials: { url: databasePath },
});
```

### generate

- run `bunx drizzle-kit generate --name <name>` after a schema change
- keep `drizzle/*.sql`, `drizzle/meta/*_snapshot.json`, and `drizzle/meta/_journal.json` together in one change
- do not copy, merge, or restore SQL files without their matching snapshots and journal entry

### review

- review every generated SQL statement before it reaches a shared database
- inspect table rebuilds, copied columns, foreign-key actions, constraints, indexes, and destructive statements
- a generated sqlite table rebuild under `0.31.10` cascades deletes and is destructive until review proves otherwise
- stop if a migration prefix collides or the journal does not match the SQL files

### apply

- make a recoverable database backup before a SQLite table rebuild
- apply reviewed migrations with `bunx drizzle-kit migrate`
- use `bunx drizzle-kit push` only for a disposable local development database

## source state

window: 2026-02-18 through 2026-08-18

- 2026-03-17: [`drizzle-kit@0.31.10`](https://www.npmjs.com/package/drizzle-kit/v/0.31.10) entered the stable package channel
- 2026-03-27: [`drizzle-orm@0.45.2`](https://github.com/drizzle-team/drizzle-orm/releases/tag/0.45.2) became the stable release and fixed `sql.identifier()` and `.as()` escaping
- 2026-03-27: the stable tag contains the [Bun SQLite driver](https://github.com/drizzle-team/drizzle-orm/tree/0.45.2/drizzle-orm/src/bun-sqlite) and [Bun SQLite usage](https://github.com/drizzle-team/drizzle-orm/blob/0.45.2/integration-tests/tests/bun/sqlite.test.ts)
- 2026-04-06: [GHSA-gpj5-g38j-94v9](https://github.com/drizzle-team/drizzle-orm/security/advisories/GHSA-gpj5-g38j-94v9) identified `<=0.45.1` as affected and `0.45.2` as patched
- 2026-05-17: [issue 5774](https://github.com/drizzle-team/drizzle-orm/issues/5774) reported stable `0.31.10` snapshot overwrite when `_journal.json` is stale
- 2026-05-19: [issue 5782](https://github.com/drizzle-team/drizzle-orm/issues/5782) reported cascade data loss during stable SQLite table-rebuild migrations
- 2026-08-18: the official [migration FAQ](https://orm.drizzle.team/docs/faq) was reviewed for local-only `push`
