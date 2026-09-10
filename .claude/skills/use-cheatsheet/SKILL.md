---
name: use-cheatsheet
description: only-if-asked
---

use(key)
  load ./{key}.md

mk(key)
  skills.search({key}, deep, recent, docs, libs)
  skills.guides.spec
  log cheatsheet out=./{key}.md

# rules

- a cheatsheet covers one lib
- a cheatsheet never contains project specific terminology or intent, i.e. it is generic and not prescriptive
- refs is a guides compliant footer
- tips is a quick list of gotchas and hints (1 line per tip, ≤ 100 chars)
- count(exemplars) ≤ 10

```md:form:cheatsheet
# {lib}

{exemplars}

{tips}

{refs}
```

## exemplar

- an exemplar uses library vocabulary or neutral placeholders, never project names or paths
- advanced pseudocode pattern
- an expression is any idiomatic block
- avoid describing edge cases; prefer strong and robust patterns
