# tests

```text
tests/
  world/
    index.{ext}
      ├ check(case Case)
      └ init() World
    types.{ext}
      └ World, Case
    setup.{ext}
      ├ setup()
      └ teardown()
    … fixtures
  {exp}.{ext}
    └ cases
  …
```

## types

```any:types
interface World {
  state: map<string, any>
  facts: map<string, () → boolean>
  api: map<string, (args) → void>
}

interface Case {
    key
    claim
    check(w World)
      … prepare state
      … assert facts
}
```

## setup

- on batch start, run setup
- on batch end, run teardown
- tests do not run before setup is complete

## world

- state preparation is part of the case check

```any:surface
check(case Case)
  log case.key — case.claim
  try
    case.check(init())
  catch
    log fault
```

```any:private
init() World
```

## exp

- exps are behavioral intent over layers
- exps import world, i.e. exps do not import fixtures or other exps
- exps are distinct, i.e. exps are not duplicate or redundant
- cases are distinct
- a case claim is a testable assertion, e.g. a check on state
- a case sketch follows skills.mk.sketch

```any:private
cases ≔ …
cases.each(world.check)
```
