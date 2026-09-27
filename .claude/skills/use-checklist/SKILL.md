---
name: use-checklist
description: only-if-asked
---

use-checklist(key)
  skills.use-checklist.{key}
  log evaluation

# rules

- rules declare the evaluation criteria
- md:form:check`- [ ] {fact} = {resolver}`
- 1 ≤ count(checks) ≤ 7
- 1 ≤ count(rules) ≤ 3

```md:form:checklist
# {key}

{rules}

## {label}

{checks}

…
```
