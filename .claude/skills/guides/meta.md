# metaform

```sql:types
field(
    type pk type
    optional nn bool
)

model(
    key pk key
    map nn map<text,field>
)

layer(
    key pk key
    name nn name
    model nn → model.key
    props nn text
    layers nn array<layer>
    checks nn array<check>
)
```

model:
    frontmatter

## filesystem

- tree

# plan

step(
    tkey pk → entity.tkey
    ins nn array<tkey>
    outs nn array<tkey>
)

step(
    ins nn array<tkey>
    outs nn array<tkey>
    idx nn int2
    uq(out,idx)
    foe nn array<glob>
    super nn → step.out
)

## filesystem

- tree
