# skill

- variables are inferred by matching name
- the signature block is the preamble

```md
{name}({params})
  {step}
  …
```

## step

- match: step
    | md:step-condition`if … log …` | `else if … log …` | `else … log …` | etc
    | md:step-call`skills.{name}({args})`
    | md:step-bind`… {body} as {variable}`
    | md:step-functional`{value}.{operation}({body})`
    | md:step-log`log {body}`
    | md:step-wait`wait {condition}`
- count(chars(step)) < 100
- is atomic
- has real consequences, e.g. logs to stdout or changes a concrete object
