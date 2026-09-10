---
name: use-checklist
description: only-if-asked
---

use(key)
  load ./{key}.md
  log evaluation

mk(key)
  log checklist out=./{key}.md

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
