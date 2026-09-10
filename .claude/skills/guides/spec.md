# spec

[ex1](./spec.ex1.md)

- vendor layers, e.g. domain services, are denoted vendor[{name}] e.g. `vendor[mesh].send(…)`
- external layers, e.g. workspace packages, are denoted ${name} e.g. `$db.rpc(…)`

```md:form:frame
{frontmatter?}

{root?}

{layers?}
```

## economy

- elementary relationships are expressed in ordinary domain language
- pseudocode is reserved for behavior whose alternatives change an outcome
- code identifiers are retained only where their exact spelling is contractual
- each requirement appears once in its owning layer
- data shapes include only fields needed to state a contract
- formatting follows the information rather than a fixed content ratio
- reduction revisions decrease both non-whitespace lines and characters

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

## pseudocode

- pseudocode is lang idiomatic and functional style
- specs may introduce simple conventions that are not described in pseudocode forms

Examples:

```{lang}:form:types
{type}
```

```{lang}:form:{surface|private}
{state}
…

{signature}
    {logic}

<!-- e.g. logic -->

{signature}
    set {name}[{predicate}] {field} = {value}
    ${layer}.{name}({args})
    vendor[{alias}].{name}({args})
    … wait for {event}
    …
…
```

### rules and logic

- pseudocode logic prefers short simple semantic expressions over correct code syntax
- rules refer to architectural roles, protocols, and occasionally code tokens
- permitted code name tokens:
  - essential and non-elementary objects, e.g. private functions
  - self-explanatory code tokens, e.g. “{name}” is equivalent to the semantic {name}
- forbidden code name tokens:
  - elementary expressions, e.g. well-known primitives
  - overly and unnecessarily prescriptive names, e.g. "{unconventional-name}.{module-assignment}"
  - highly driftable names, i.e. that are likely to change over time

### http

- server api surfaces use http request blocks
- request lines retain methods, paths and contractual query parameters
- `#` lines are spec annotations outside the wire format
- response annotations state result meaning and outcome-changing conditions
- shared authentication and response conventions appear once before the block
- headers and bodies appear only when needed to state the contract

```http:form:surface
{METHOD} /{path}?{parameter}={value}
# {response meaning}
# {condition} → {outcome}

{METHOD} /{path}
{Header}: {value}

{body}
# {response meaning}
```

### sql

- selected field mutation is `set {name}[{predicate}] {field} = {value}`

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
