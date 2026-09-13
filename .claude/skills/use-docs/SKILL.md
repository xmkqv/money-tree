---
name: use-docs
description: only-if-asked
---

pre-call-hook:
  key = {lang}-{key} if infer.lang else {key}

use-docs(key)
  if ¬exists(skills.use-docs.{key})
    mk(key)
  skills.use-docs.{key}

mk(key)
  skills.search(key, deep=true, recent=true, repos=true)
  use mintlify-index, then context7
  skills.guides.spec
  log out=skills.use-docs.{key}

# rules

- a cheatsheet covers one lib
- a cheatsheet never contains project specific terminology or intent, i.e. it is generic and not prescriptive
- refs follows skills.guides.spec.refs
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
