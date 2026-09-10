---
name: use-command
description: only-if-asked
---
# command

- flags are expanded (i.e. not shorthand) and explained (once, with a simple plain english inline definition)
- a tight command is minimal, precise, and consistent with the command manual
- commands are not over-engineered
- command implementation is elegant and readable
- command is bash
- prefer established tools, e.g. fswatch, to custom scripts

```bash:form:patterns
cooltool
  --property-flag-we-use {value} # short and plain explanation
  --…
…
```

command()
  log intent
  skills.search(deep, recent) for modern tools, bash commands, and terminal patterns
  log 5 tight exemplars
