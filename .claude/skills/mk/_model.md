# model

model()
    skills.guides.spec
    analyze context, layer, task
    loop until approved
        log insights
        log intent delta
        any of
            log architecture delta
            log spec tree delta
            log protocols delta
            log invs delta
        log questions, exemplars, and foils
        wait for designer

```md:form:model
{intent}

{skills.mk.sketch[]}

{invs}

{exemplars}
```

```md:form:exemplar|foil
# [{idx}] {good/bad-quality}

{block}
```

## rules

- question = md:form:question`[{idx}] {question}`
- count(intent.lines) ≤ 3
- final model is the tightest possible expression of intent
- delta can be empty
- insights explicitly connect any information available to the intent
- the loop continues until the designer explicitly approves stopping
