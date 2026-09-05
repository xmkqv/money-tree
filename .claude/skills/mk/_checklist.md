# checklist

checklist(name, subject=infer())
  write skills.use.{name}
    verdict
    decisive check
    items ordered by cost ascending
    exceptions

# rules

- a checklist is a module at skills.use.{name}
- a checklist name is the failure it detects
- a checklist covers one subject
- a verdict is binary
- items are independent, i.e. no item entails a co-item
- count(items) ≤ 7
- a threshold maps count(flags) to the verdict

```md:form:checklist
# {verdict}

{decisive}

{items}

{exceptions?}
```

## decisive

- the decisive check is the ground truth the items approximate
- the decisive check is one question
- the decisive check names the evidence that settles it
- a corollary restates the decisive check more cheaply

```md:form:decisive
**{question}?** {evidence that settles it}

{corollary?}
```

## item

- an item covers one signal
- an item resolves to yes or no
- an item resolves by inspection, i.e. without running the subject
- an item cites where its evidence sits
- an item names the failure it detects, not the virtue it wants
- yes means the flag holds
- an item is falsifiable, i.e. some subject answers no

```md:form:item
{idx}. **{flag}** — {question}?
```

## exception

- an exception states when a flag is correct
- an exception names the class it covers
- an exception carries the rule that replaces the flag

```md:form:exception
{class} — {why the flag is correct} — {replacing rule}
```
