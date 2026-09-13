---
name: guides
description: only-if-asked
---

guides: spec,code

router(keys=infer())
  keys.each(skills.guides.{key})

- skill references use `skills.{dotpath}`, including sections, e.g. `skills.guides.names`
- resolve Markdown prose line-length violations by rephrasing; keep checklist items on one line

# names

- tkey (token-key) = an indivisible and composable reference, e.g. when formulating code tokens

```sql:types
banned_names = [ … familial names for graph and tree concepts ]

re_tkey = "^[a-z]+$"
re_name = "^[a-z][a-z0-9]+$"
re_line = "^\S[\S ]+$"

domain name = text check(re_name.test and name ∉ banned_names)
domain line = text check(re_line.test and count(words) ≤ 20)
domain tkey = text check(re_tkey.test)

entity(
    tkey pk tkey check(tkey is derived from name)
    name nn uq name
    idea nn uq line check(name ∉ idea)
)

tkeys() → set(entity.tkey)
```

# forms

```sql:types
enum lang { md, ts, py, … }

form(
    name nn → entity.name
    lang nn lang
    glob nn text
    pk(lang, name)
)
```
