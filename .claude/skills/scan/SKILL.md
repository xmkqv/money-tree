---
name: scan
description: only-if-asked
---

scan(spec?)
  fov=./**/*
  foe=fov (iff ¬spec then excl spec)
  skills.guides
  log intent
  layers = infer(fov)
  log fov, layers
  layers.each(scan-layer)

scan-layer(layer)
  skills.mk.tree
  skills.mk.sketch(protocols)
  fix basic issues
  fix dof issues incl remove dead-code
  fix tests issues incl remove bad-tests
  fix code issues
  log report

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

## basic

- typos
- grammar
- simple lint issues
- voice asd-ste100
- names consistency

## dof

- duplication
- redundancy
- over-engineering
- spaghetti
- legacy echoes

## code

- skills.guides.code.infer()
- spec satisfiability
- idiomatic pattern matching
- skills.use-cheatsheet(infer())

## tests

- skills.guides.code.tests
- skills.use-checklist.use(bad-tests)
