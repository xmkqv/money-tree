---
name: search
description: only-if-asked
argument-hint: "[query] [deep?] [recent?] [repos?]"
---

search(query=infer(), deep?, recent?, repos?)
  if deep, spawn 3 agents and design explorative queries
  use web search
  if recent, filter results from the last 6 months
  log results
  if repos, log repos as table

```md:form:search-result
[{idx}] {claim}

{detail}

{refs}
```

```sql:types
repo(
  link pk
  last_active nn datetime
  stars nn integer
  dx nn integer
  features nn array<text>
)
```

# rules

## details

- prose is declarative
- for code, focuses on advanced exemplars
- logs to stdout if not specified