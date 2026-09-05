---
name: score
description: only-if-asked
disable-model-invocation: true
argument-hint: "[fov=infer()]"
---

score(fov)
  log index
  log scorecard-faults(fov)
  log scorecard-merits(fov)
  log cut candidates as a diff

# rules

- every header, prose line, and comment is a row
- a fence is one row
- code is one row per contiguous block
- score ≔ mean(merits) - mean(faults)
- a score axis is an integer ∈ [0,5]
- an ambiguous axis is null
- a cut first drops lines then refactors to preserve useful intent

```md:form:index
| {idx} | {kind} | {path(fragment)?} |
```

```md:form:scorecard-merits
| {idx} | {merits,sep="|"} | {mean} |
```

```md:form:scorecard-faults
| {idx} | {faults,sep="|"} | {mean} |
```

## merits

- unique: no co-row states it
- original: the content is not the default answer
- purposeful: removal changes an outcome
- correct: it holds under the next test of the reader
- atomic: it carries one obligation

## faults

- claudy: the voice hedges or narrates
- overlap: a row in scope already covers it
- overreach: it binds material outside its layer
- uneconomic: its premise costs more than it returns
- tautological: it adds value only defined by its premise
- obsequious: the voice fawns or defers
