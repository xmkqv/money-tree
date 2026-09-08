---
name: search
description: only-if-asked
argument-hint: "[deep?] [recent?] [libs?] [docs?]"
---

search(deep?, recent?, libs?, docs?)
  if deep, spawn 3 agents and design explorative queries
  if recent, filter results from the last 6 months
  if docs, use mintlify-index, then context7
  else use web search
  log search results
  if libs, log libs table

```md:form:search-result
[{idx}] {claim}

{detail}

{refs}
```

```md:form:libs
| link | last active | stars | developer experience | feature tags |
|------|-------------|-------|----------------------|--------------|
```

# rules

## details

- prose is declarative
- prose lines are short (< 100 chars) bulleted items
- for code, focuses on advanced exemplars
