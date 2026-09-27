---
name: scan
description: only-if-asked
---

scan(cat=*,lvl=*,fix?)
  log intent, fov, foe
  log skills.mk.sketch(tree spec)
  log issue[cat,≤lvl]
  if fix then run matching fix_*

# rules

- spec > code

```md:form:report
# {layer}

{fails}

{conclusion}
```

## issue flavors

| cat   | foe  | lvl |
|-------|------|-----|
| typos | spec | 0   |
| voice | spec | 0   |
| lint  | code | 0   |
| names | spec | 1   |
| dof   | code | 1   |
| tests | code | 1   |

fix_typos()
  fix foe

fix_voice()
  log asd-ste100 rules (25 line max)
  fix foe

fix_lint()
  fix foe

fix_dof()
  log check(foe,skills.use-checklist.code)
  rm bad code
  rm duplication
  rm redundancy
  rm legacy echoes

fix_tests()
  log check(foe,skills.use-checklist.tests)
  rm bad tests

## observer

- spawn happens **after** your scan
- observer is **not aware** of its observer status
