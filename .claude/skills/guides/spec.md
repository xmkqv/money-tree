# spec

[ex1](./spec.ex1.md)

- content ratios = 80% syntax, 10% prose, 10% any (globally, per layer, per form)
- vendor layers, e.g. domain services, are denoted vendor[{name}] e.g. `vendor[mesh].send(…)`
- external layers, e.g. workspace packages, are denoted ${name} e.g. `$db.rpc(…)`

```md:form:frame
{frontmatter?}

{root?}

{layers?}
```

## frontmatter

- `name:` names the spec
- `vendors:` maps each role alias to its vendor, e.g. `mesh: iroh`

## layers

- layers are hierarchical, i.e. specificity(layer) > specificity(context(layer))
- layers are balanced, i.e. specificity(layer) ≈ specificity(co-layers(layer))
- layers are distinct, i.e. non-overlapping
- count(rules) ≤ 7

```md:form:blocks
{types?}

{surface?}

{private?}
```

### root

- exps are broad declarative design register claims about consumer experience
- exps are similarly weighted, i.e. similarly leveled in importance and complexity
- count(exps) ≤ 7

```md:form:root
{exps}

{blocks}

{invs?}
```

## names

- names converge over time, i.e. state is optimal iff each thing has 1 name
- names are canonical (i.e. well-known) or conventional (i.e. in spec)
- `nn` = not null

## pseudo-code

- pseudo-code syntax is idiomatic and flexible
- selected field mutation is `set {name}[{predicate}] {field} = {value}`
- comma-separated assignments after one selector form one atomic field mutation
- prose describes protocols and architectural roles
- logic can alternate between syntax and prose
- inv:{predicate} → error declares a failure mode
- a cron declaration is `cron:{name}[{period}]()`

Examples:

```{lang}:form:types
{type}
```

```{lang}:form:{surface|private}
{state}
…

{signature}
    set {name}[{predicate}] {field} = {value} -- e.g. syntax
    ${layer}.{name}({args}) -- e.g. external layer
    vendor[{alias}].{name}({args}) -- e.g. vendor
    … wait for {event} -- e.g. prose
    …
…
```

### sql

```sql:form:types
enum {enum} { … }
…
type {type} = ( … )
…

{name}(
    id pk
    key nn uq text check(len(key) > 0 and has no numbers)
    def → defs.key
    another_tbl_id nn uq → another_tbl.id
    …
    check(a = b)
)

-- given name(id,data)
vw_…(name:*) → ( name_id, name_data )
vw_…(name.*) → ( id, data )
```

```sql:form:private
{name}({args}) {out} {mods}
    -- {steps,sep=;}

{name}({p_arg} {type},…) {out} {mods}
    … {steps}

trg name before|after event[|event] [deferred] table [when predicate] [callable()]

policy on {tables} [{alias}] to {roles}
    {op} using ({predicate})
    {op} with check ({predicate})
```

### ts/tsx

- selectors are , e.g. `{Name}`, `{Name} > {Name}`, etc
- styles are semantic config, e.g. `{attribute} = {value}`, `like {exemplar}`, etc

```ts:form:css
{selector} — {style}
...
```

```ts:form:types
type {Name} = {primitive} branded {Name}
type {Name} = "{member}" | …

interface {Name} {
    {name}: Accessor<{type}>
    {name}({args}): {out}
    …
}

type {Name} = { … }
```

```ts:form:surface
{name}({args})
    [{value},set{Value}] = createSignal<{type}>({init})

    onMount(
        {step}
        …
    )

    → (
        {member}
        {name}({args})
            {step}
    )

{Name}Ctx = createContext<{Name}>()
use{Name} = () → useContext({Name}Ctx) ?? panic("{message}")
```

```ts:form:private
{name}({args})
    {logic}
    … {steps}
    → {out}
```

```tsx:form:surface
{Name}Element({props})
    {binding} = use{Name}()
    [
      class={name}
      {attribute}={value}
      --{property}={value}
      …
      on {event} → {handler}
    ]
        {Name}Element({args})
        {collection}.map({Name}Element)

{Name}Element({props})
    [class={name}]
    switch {props}.{discriminant}
        {case} → ...{props}
        …
```
