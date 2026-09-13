# skill

- entity names and tkeys follow skills.guides.names
- notation follows skills.guides.forms and skills.guides.spec.glyphs
- variables are inferred by matching name
- the signature block is the preamble

```md:form:skill
{name}({params})
  {step}
  …
```

## step

- match: step
    | md:form:step-condition`if … log …` | `else if … log …` | `else … log …` | etc
    | md:form:step-call`skills.{name}({args})`
    | md:form:step-bind`… {body} as {variable}`
    | md:form:step-functional`{value}.{operation}({body})`
    | md:form:step-log`log {body}`
    | md:form:step-wait`wait {condition}`
- count(chars(step)) < 100
- is atomic
- has real consequences, e.g. logs to stdout or changes a concrete object
