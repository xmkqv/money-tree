---
name: scan
description: only-if-asked
---

scan(spec?,observer?)
  fov=./**/*
  foe=fov (iff ¬spec then excl spec)
  skills.guides
  log intent
  layers = infer(fov)
  log fov, layers
  layers.each(scan-layer)
  if observer
    spawn an agent to repeat the scan
    log both reports paths
    log every fix the observer agent caught that you did not

scan-layer(layer)
  skills.mk.tree
  skills.mk.sketch(protocols)
  flavors.each(fix)
  log report

fix(flavor)
  log flavor, rules
  log foe.issues
  solve issues

# rules

- spec > (code, tests)
- spec is authoritative over code and tests, i.e. code and tests are realizations of spec
- log files are written to /tmp/{rnd}.md
- spec bugs materialize as failing tests
- if count(tests.fails) == 0 → conclusion = `code and tests match or extend spec; spec has no bugs`
- if count(tests.fails) ¬= 0 → conclusion = `{reasons}`

```md:form:report
# {layer}

{fails}

{conclusion}
```

## issues flavors

### basic

- typos
- inhuman grammar
- lint
- voice asd-ste100 mismatch
- names inconsistency

### dof

- skills.use-checklist.dead-code matches
- duplication
- redundancy
- legacy echoes

### code

- skills.guides.code.infer() non-compliance
- skills.use-cheatsheet.infer() missed opportunities
- drift from spec
- non-idiomatic patterns

### tests

- skills.guides.code.tests non-compliance
- skills.use-checklist.bad-tests matches

## observer

- spawn happens **after** your scan
- observer is **not aware** of its observer status