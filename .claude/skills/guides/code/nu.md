# nu

## form

- nushell:form:code`*`

## types

### typed main

```nushell
def main [catalog: path, --limit: int = 50] { open $catalog | first $limit }
```

[scripts](https://www.nushell.sh/book/scripts.html)

### module surface

```nushell
export def shelved [db: path] { open $db | get book | where shelf_id != null }
def normalize [] { str trim | str lowercase }
```

[creating modules](https://www.nushell.sh/book/modules/creating_modules.html)

## flow

### row pipeline

```nushell
open library.db | get book | where shelved | sort-by added_at | select id title
```

[working with tables](https://www.nushell.sh/book/working_with_tables.html)

### native sqlite traversal

```nushell
open library.db | get loan | where state == "open"
```

[loading data](https://www.nushell.sh/book/loading_data.html#sqlite)

### bound query

```nushell
open library.db
| query db "select id, meta from book where shelf_id = ?" -p [$shelf]
| update meta { from json }
```

[query db](https://www.nushell.sh/commands/docs/query_db.html)

### allowlisted identifier

```nushell
let col = ($allowed | where $it == $name | first)
open library.db | query db $"select ($col) from book where id = ?" -p [$id]
```

[sqlite parameters](https://www.sqlite.org/lang_expr.html#parameters)

## state

### persisted table

```nushell
$books | into sqlite library.db -t book
```

[into sqlite](https://www.nushell.sh/commands/docs/into_sqlite.html)

### returned mutation

```nushell
open library.db | query db "delete from loan where state = 'returned' returning id"
```

[returning](https://www.sqlite.org/lang_returning.html)

## boundaries

### schema inspection

```nushell
open library.db | schema | get tables.book.columns
```

[schema](https://www.nushell.sh/commands/docs/schema.html)

### strict table with json column

```sql
create table book (
  id integer primary key,
  title text not null,
  meta text check(json_valid(meta))
) strict
```

[strict tables](https://www.sqlite.org/stricttables.html)
