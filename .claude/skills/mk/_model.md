# model

model()
    skills.guides.spec
    analyze context, layer, task
    ask questions
    loop until approved
        log insights
        log intent delta
        any of
            log architecture delta
            log spec tree delta
            log protocols delta
            log invs delta
        wait for designer

```md:form:model
{intent}

{skills.mk.sketch[]}

{invs}
```

## rules

- count(intent.lines) ≤ 3
- final model is the tightest possible expression of intent
- delta can be empty
- insights explicitly connect any information available to the intent
