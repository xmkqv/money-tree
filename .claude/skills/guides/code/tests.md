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

```any:private
batch(cases)
  setup()
  try
    cases.each(world.check)
  finally
    teardown()
```

## world

```any:surface
check(case Case)
  log case.key — case.claim
  try
    case.check(init())
  catch
    log fault
    throw fault
```

```any:private
init() World
```

## exp

- exps import world, never fixtures or other exps
- exps are distinct
- cases are distinct
- a case claim is a testable assertion
- a case sketch follows skills.mk.sketch()

```any:private
cases = …
cases.each(world.check)
```
