---
name: use-checklist
description: only-if-asked
---

use-checklist(key)
  if ¬exists(skills.use-checklist.{key})
    mk(key)
  skills.use-checklist.{key}
  log evaluation

mk(key)
  log out=skills.use-checklist.{key}

# rules

- rules declare the evaluation criteria
- md:form:check`- [ ] {fact} = {resolver}`
- 1 ≤ count(checks) ≤ 7
- 1 ≤ count(rules) ≤ 3

```md:form:checklist
# {key}

{rules}

## checks

{checks}
```
