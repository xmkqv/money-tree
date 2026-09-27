---
name: money-tree-quant-strategy-check
description: only-if-asked
argument-hint: "[strategy] [cases?]"
---

money-tree-quant-strategy-check(strategy, cases=infer())
  log intent, fov
  log skills.mk.sketch(tree spec)
  log skills.mk.sketch(tree code)
  skills.search(equations governing {strategy.family}, deep=true) as basis
  log basis
  cases.each(simulate)
  cases.each(validate)
  log report

simulate(case)
  log givens
  log expected = basis(givens)
  loop until terminal
    log tick as trace row
  log outcome

validate(case)
  log faithful
  log consistent
  log grounded
  log issues

# rules

- skills.guides.spec
- foe = ∅
- fov = the strategy layer, its variation, its module, and the strategy base
- spec > code
- basis ≠ spec → a question for the designer, never an issue
- no code runs and no test is written

## basis

- an equation is pseudomath over glossary names and code names
- an equation carries a ref per skills.guides.refs
- count(equations) ≤ 7

## simulation

- state evolves as logged text, never as executed code
- expected precedes the first trace row
- a trace row is one tick: ( t, input, path, state )
- path = the branch taken, cited by file and line
- state = holding fields ∪ candidates ∪ portfolio calls
- givens are round numbers, so expected is computable by hand
- terminal ∈ { exit, session close, steady state, count(rows) = 12 }

## cases

- givens fully determine the outcome
- cases ⊇ { known answer, threshold equality, degenerate input, short direction, paused or capped }
- one case settles one claim

## verdicts

- faithful = ∀ path ∈ trace: code(path) ≡ spec
- consistent = outcome = expected
- grounded = ∀ row ∈ trace: row.state ⊨ basis
- issue.owner ∈ { spec, code }
- conclusion = `{issues}` if count(issues) ≠ 0 else `pass`

```md:form:basis
# basis

[{idx}] {equation}
    {ref}
…
```

```md:form:case
## [{idx}] {case}

givens: {name} = {value}; …
expected: {outcome}

| t | input | path | state |
|---|-------|------|-------|
| … | … | … | … |

outcome: {outcome}
```

```md:form:report
# {strategy}

{skills.mk.sketch(tree spec)}

{skills.mk.sketch(tree code)}

{basis}

{cases}

| case | faithful | consistent | grounded | issue |
|------|----------|------------|----------|-------|
| … | … | … | … | … |

{conclusion}
```
