# recs

recs(max?)
  log intent
  log recs.sort(by=coupling descending).slice(max)

```md:form:rec
# [{idx}] {bad} → {good}

{deps?}

{diff}
```

```md:form:deps
succedes [{idx},…]
precedes [{idx},…]
```

## rules

- count(recs) ≤ max
- diff is concrete diff on active files
- count(rec.deps) ≤ 3
- rec.diff is atomic
