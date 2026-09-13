---
name: scan
description: only-if-asked
---

out=stdout

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
    log every fix the observer agent caught that you did not
  after completion:
    cheating tests workaround spec bugs
    cheating tests intentionally obfuscating performance for malicious reasons
    if there are cheating tests at the end of your scan, you are responsible for the consequences

scan-layer(layer)
  log skills.mk.sketch(tree)
  log skills.mk.sketch(protocols)
  analyze layer files
  flavors.each(fix)
  log report

fix(flavor)
  log flavor, rules
  log foe.issues
  solve issues

# rules

- spec > (code, tests)
- spec is authoritative over code and tests, i.e. code and tests are realizations of spec
- spec bugs materialize as failing tests
- count(tests.fails) ≠ 0 → conclusion = `{reasons}`

```md:form:report
# {layer}

{fails}

{conclusion}
```

## issue flavors

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
- skills.use-docs.infer() missed opportunities
- skills.use-checklist.good-code anti-patterns
- any code that is not a directly inferrable from spec
- non-idiomatic patterns

### tests

- skills.guides.code.tests non-compliance
- skills.use-checklist.bad-tests matches

## observer

- spawn happens **after** your scan
- observer is **not aware** of its observer status
