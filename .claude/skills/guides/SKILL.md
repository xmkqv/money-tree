---
name: guides
description: only-if-asked
---

guides(paths=infer())
  load ./{path}.md for each path

[glyphs](./glyphs.md)
[forms](./forms.md)
[spec](./spec.md)
[code](./code/index.md)
[libs](./libs/index.md)

# rules

- rules are atomic, i.e. exactly one claim
- rules are lowercase
- rules are predicative
- count(rules) ≤ 7
- obvious conventions are considered soft rules
- rules refer to architectural roles; a naming rule may cite the token it prescribes

```md:form:rules
- {rule}
- …
…
```

# refs

- uris: `[…](uri)`
- footer: `[…][key]` where `[key]: …` is declared in a `{hashes} refs` section at the doc foot

# nits

- graph and tree terms are "list", "first", "last", "sub{name}s", "co{name}s", "container", etc, not familial terms
- {name}_of(…) is not a function name
