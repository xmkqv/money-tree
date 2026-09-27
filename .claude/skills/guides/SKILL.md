---
name: guides
description: only-if-asked
---

guides: spec,code

router(keys=infer())
  keys.each(skills.guides.{key})

- skill references use `skills.{dotpath}`, including sections, e.g. `skills.guides.names`
- a prose line over the limit is rephrased, not wrapped
- a checklist item is one line
- tkey = an indivisible and composable reference to an entity, e.g. when formulating code tokens

```sql:types
banned_names = [ … familial names for graph and tree concepts ]

re_tkey = "^[a-z]+$"
re_name = "^[a-z][-a-z0-9]+$"
re_line = "^\S[\S ]+$"

domain name = text check(re_name.test and name ∉ banned_names)
domain line = text check(re_line.test and count(words) ≤ 20)
domain tkey = text check(re_tkey.test)
domain glob = text check(is glob)

entity(
    tkey pk tkey check(tkey is derived from name)
    name nn uq name
    idea nn uq line check(name ∉ idea)
)

tkeys() → set(entity.tkey)

enum lang { md, ts, py, … }
domain regex = text check(is regex)

form(
    name nn → entity.name
    lang nn lang
    regex nn regex
    pk(lang, name)
)
```

# refs

- md:form:ref-key`{ns}:{slug}`, where ns is any arbitrary namespace
- ref keys are unique
- the root docs entrypoint of a lib's docs is keyed `{lib}:docs`
- a label is the sentence's own words, never an echo of its key
- a ref stands alone; it need not be cited in the text
- tips are (optional) critical and immediately useful verbatim extracts (≤ 80 chars)
- a tip is a complete, self-standing clause; never a mid-sentence cut
- a tip is one line, indented 4 spaces; the next definition follows a blank line

```md:form:refs
# refs

[{key}]: …
    {tip?}
    …
…
```