---
name: scan
description: only-if-asked
---

scan(fov=infer())
  log intent
  layers ≔ infer(fov)
  log fov, layers
  layers.each(
    fix basic issues
    fix lexicon issues
    fix dof issues
    log code issues
    log drift_log
  )

# rules

- authority: (guides, spec) > (code, tests)
- auto-fixes consider guides and spec authoratitive over code and tests

## basic

- typos
- grammar
- simple lint issues

## lexicon

- skills.guides.*
- voice asd-ste100
- names consistency
- idiomaticity

## dof

- duplication
- redundancy
- over-engineering
- spaghetti
- legacy echoes

## code

- skills.guides.code.infer()
- spec satisfiability

# drift log

- table:log cols ≔ name, cat, in spec, in code
- cat ∈ pattern, function, type, variable, constant, config, secret, {other}
- count(spec sketches) = count(code sketches)
- check log.names.each ∈ sketches.names

```md:form:drift-log
# drift

{table:log}

## spec sketches

{sketches}

## code sketches

{sketches}
```
