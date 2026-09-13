# recs

recs(max=null)
  skills.guides.spec
  log intent
  log skills.mk.sketch(code tree)
  log recs in phases

```md:form:phase
# [{idx}] {intent}

{dv}

{recs}
```

```md:form:rec
## [{step}] {intent}

{dv}

{diff}
```

## rules

- count(recs) ≤ max
- idx ≥ 1
- step = md:form:step`{idx}:{sub-idx}`
- diff is concrete diff on current files
- dv is the delta volume
- phases group recs by layer
- layers are decoupled
