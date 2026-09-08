---
name: catalogs
description: only-if-asked
---

# rules

- catalog access requires a user request or an active skill call
- trim redundant catalog entries
- catalogs are informational or comparative references
- catalogs do not contain executable spec or rules
- comparative catalogs may contain scoped intent and analysis
- catalogs are self-contained

# forms

- facts follow the rule style in [guides](../guides/SKILL.md)
- a comparative catalog uses the libs table form in skills.search
- a reference catalog uses the entry form below
- references are nested by relative path, i.e. subdomains stack naturally

```md
[{name}][{key}]
    {fact}
    ...

    [{sub-name}][{sub-key}]
        {fact}
        ...

## refs

[{key}]: {url}
[{sub-key}]: {url}
```
