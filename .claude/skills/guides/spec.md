# spec

- specs may imply valid conventions beyond those provided by this guide
- specs elide trivial implementation details
- specs elide inferrable logic
- md:form:vendor`vendor[{name}]`
- md:form:service`${name}`

## frontmatter

```sql:types
frontmatter(
    name pk → entity.name
    refs array<ref>
    vendors array<vendor>
    elide array<line>
    defer array<line>
)
```

## layers

- exps are behavioral intent over layers
- sub-layers refine their container
- co-layers are balanced
- co-layers are distinct
- blocks are balanced

```sql:types
is_declarative(text)
is_design_register(text)
    → text ∌ code tokens composed from tkeys()
is_pseudomath(text)
is_pseudocode(text)
    → is functional style and idiomatic to the language
is_atomic(text)

domain rule = line check(is_declarative)
domain exp = rule check(is_design_register)
domain inv = rule check(is_pseudomath and is_atomic)

layer(
    name pk → entity.name
    container → layer.name
    rules array<exp | inv>
    check(count(exps) ≤ 7 and count(invs) ≤ 7)
)

enum block_type { types, surface, private }

block(
    name pk → entity.name
    type nn block_type
    layer nn → layer.name
    content nn text check(is_pseudocode)
)

context(layer) layer[]
    → walk layer.container
```

## glyphs

Glyphs follow language and local conventions; forms define patterns, and undeclared notation remains inferable.

- binding and comparison: `=` binds or compares; `≠ ≡ ≈ < ≤ > ≥`
- sets and logic: `∈ ∉ ∋ ∌ ⊆ ⊇ ∪ ∩ ∖ ∅ ¬ ∃`
- flow, references, and implication: `→`; `↛` does not imply
- arithmetic and change: `+ - * / ± Δ`
- forms: `{name}` slot; `{name?}` optional; `{a|b}` choice; `{name,sep=;}` expansion
- elision: `…`
- prose: `—` aside or style separator; `§` section; `·` separator

## pseudocode

Examples:

```{lang}:form:types
{type}
…
```

```{lang}:form:surface|private
{state}
…

{signature}
    {logic}
…
```

- mutation: `set {name}[{predicate}] {field} = {value}`
- service: `${name}.{method}({args})`
- wait: `wait for {…}`
- vendor: `vendor[{alias}].{method}({args})`, `vendor[{alias}].{property}`

### http

```http:form:surface
{METHOD} /{path}?{parameter}={value} → {out}
# {logic}

{METHOD} /{path}
{Header}: {value}
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

- selector rules are named elements or structural relations between named elements, e.g. `{Name}` or `{Name} > {Name}`
- styles are semantic config, e.g. `{attribute} = {value}`, `like {exemplar}`, etc

```ts:form:css
{selector} — {style}
…
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

## refs

- uris: `[…](uri)`
- footer: `[…][key]` where `[key]: …` is declared in a `{hashes} refs` section at the doc foot
