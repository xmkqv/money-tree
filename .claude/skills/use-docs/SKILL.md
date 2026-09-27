---
name: use-docs
description: only-if-asked
---

use-docs(key)
  lang = infer(lang) ∈ { py, rs, ts }
  if ¬exists(skills.use-docs.{lang}.{key})
    create(lang, key)
  skills.use-docs.{lang}.{key}

create(lang, key)
  skills.search(key, deep=true, recent=true, repos=true)
  use mintlify-index
  use context7
  skills.guides.spec
  log out=skills.use-docs.{lang}.{key}

# rules

- a cheatsheet covers one lib
- a cheatsheet never contains project specific terminology or intent, i.e. it is generic and not prescriptive
- refs follows skills.guides.spec.refs, which carries the gotchas as tips
- count(exemplars) ≤ 10

```md:form:cheatsheet
# {ref:lib}

{exemplars}

{refs}
```

## exemplar

- an exemplar uses library vocabulary or neutral placeholders, never project names or paths
- an exemplar is an advanced pseudocode pattern
- an expression is any idiomatic block
- an exemplar omits edge cases
- an exemplar shows a strong, robust pattern
