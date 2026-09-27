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
    conventions array<line>
    reminders array<line>
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

layer(
    name pk → entity.name
    container → layer.name
    rules array<exp>
    check(count(exps) ≤ 7)
)

enum block_type { types, surface, private, invs }

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

- invs are invariant checks
- invs tend more declarative semantics rather than concrete pseudocode
- count(invs) ≤ 3

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

```md:form:invs
invs:
    {invariant}
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

- column types may be inferred from context or references
- reference traversal follows foreign keys without spelling out joins
- inline trigger checks declare enforced predicates; names, events, and timing may remain implicit

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
    derived nn {type} generated({expression})
    …
    pk({columns})
    uq({columns}) where {predicate}
    check(a = b)
    trg check({predicate})
)

-- table-level pk and uq may span multiple columns; where is optional
-- check states a constraint; trg check requires trigger enforcement
-- generated(expression) declares a derived column

-- given name(id,data)
vw_…(name:*) → ( name_id, name_data )
vw_…(name.*) → ( id, data )

policy[{table},{…roles?}] get?=… set?=… add?=… del?=…
{op}={using?} {check(…)?}

-- get ≡ select; set ≡ update; add ≡ insert; del ≡ delete
-- omitted roles mean public
-- omitted operations declare no policy
-- using filters existing rows
-- check validates proposed rows
-- get and del accept only using
-- add accepts only check
-- set accepts using and check; omitted check inherits using
```

```sql:form:private
tile t
tile[p_id] t
join tile_xywh xywh on xywh.tile_id = t.id

{name}({args}) {out} {mods}
    -- {steps,sep=;}

{name}({p_arg} {type},…) {out} {mods}
    … {steps}

trg name before|after event[|event] [deferred] table [when predicate] [callable()]
    {steps?}

trg name after insert registry
    trg name before insert {new.tbl}
        {steps}
        → new
```

### css

- a selector is a named element, a state `{Name}[{state|state}]`, a part `{Name} .{part}`, or a relation `{Name} > {Name}`
- a state reads as its dom or aria name; `¬` negates, `∧` joins
- styles are semantic config separated by `;`: `{property} = {value}`, `{alias}`, `like {exemplar}`
- values name tokens by stem, e.g. `reading width`, `xs`, `easing geometry`, never `var(--…)`
- an alias composes tokens in prose: `{alias} ≡ {token} + {token}`
- a spec block never carries real css; syntax belongs to code

```css:form:types
--{name}
--{name}-{a,b,c}
--{name} = {value}
```

```css:form:surface
{Name} — {property} = {value}; {property} = {value}
{Name}[{state|state}] — {alias}
{Name}[{state} ∧ ¬{state}] — {property} = {value}
{Name} > {Name} — like {exemplar}; {property} = {value}
{Name} .{part} — {property} = {value}
```

### ts/tsx

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
