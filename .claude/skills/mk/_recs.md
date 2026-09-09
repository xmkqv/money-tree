# recs

recs(fov=infer(), max=null, out=null)
  log intent
  log fov, foe, and skills.mk.tree
  log recommendations.orderby(complexity ascending).slice(0, max)
  iff out, pipe to out
  log table:recs

# rules

- the title is a one-line (<100 chars) formal problem statement
- each indexed item is atomic, i.e. cover exactly one concern
- count(recommendations) ≤ max

```md:form:brief
{glossary}

{skills.mk.tree}

{recommendations}
```

```md:form:recommendation
# [{idx}]: {title}

{cases}

{solution}
```

## case

- a case is a narrow exercise clarifying one aspect of the issue
- 1 ≤ count(cases) ≤ 3

```md:form:case
## {what-it-shows}

{givens}

{sketch}
```

## solution

- a diff is a fenced unified diff on current files resolving the problem
- each diff block covers exactly one file, named on its `---` line
- non-contiguous hunks separate with `@@`, not ellipses
- 1 ≤ count(whatifs) ≤ 3
- if diff is not pure removal, whatifs include a pure reduction alternative
- the solution content is a fenced diff and nothing else

````md:form:solution
## {what-it-solves}

```diff
{diff}
```

````

## table:recs

- cols:
  - path ≔ markdown reference key
  - intent ≔ ≤70 chars, what will change
  - category ∈ validity, phrasing, consistency
  - assumes ≔ markdown reference key
- path and assumes share the skills.guides refs section
- validity is a special key reserved for provable correctness concerns
- table is a markdown table
