# model

mk-model()
    loop until approved
        log glossary
        wait for feedback
    loop until approved
        log model (max count(lines) = next(fibonacci))
        wait for feedback

```md:form:model
{intent}

{invs?}

{sketches?}
```

## rules

- the glossary is not prescriptive, i.e. it is design register and light touch
- intent is a list of design register statements
- each intent statement is a single bullet (≤ 80 chars)
- inv ≡ invariant
- an inv is a code register statement (pseudo-logic, ≤ 80 chars)
- the final model contains intent, invs, and sketches
- final model is a complete focused technical description of design intent
