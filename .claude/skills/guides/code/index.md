# code

- code is self-explanatory
- code is human-readable
- code names align with spec naming conventions
- code has no comments
- code fails fast, i.e. if an error handling branch is not declared in spec then branch panics instead of inventing a handler
- each code line reads like a sentence

general:
  [env](./env.md)
  [tests](./tests.md)
  [libs](../libs/index.md)
[css](./css.md)
[nu](./nu.md)
[py](./py.md)
[rs](./rs.md)
[ts](./ts.md)

## packages

- use the widest and latest version ranges

## invariants

- code uses early checks to narrow possible states, e.g. if predicate → panic

## modules

- generally, order module concerns: imports, types, constants, surface, private
- generally, imports of a co-module or a lower-module are relative; every other import is absolute

## names

### nouns

- types, entities, values, and nullary accessors are compact noun phrases
  - implementation qualifiers follow the role
- entity tables are singular, collections are plural
  - primary keys are bare, foreign keys are qualified
- value names expose their meaning
  - booleans are predicates
  - instants and dates end with `_at`
  - quantities end with a unit suffix, e.g. `*_ms`
  - bounded constants end with their bounds

### verbs

- side effects are verb phrases
  - `get` retrieves by key
  - `find` searches
  - mutations and transitions use explicit verbs
- related operations share one lexical stem
  - fallible operations prefix `try`
  - lazy collections prefix `iter`
- factories lead with their type
  - configuration is named, never a fluent option chain
  - one conversion verb covers every ownership mode
- predicates start with an affirmative auxiliary

### kinds

- events are `subject.past_participle`
- errors are `VerbObjectError`
- tests are outcome then condition
- generics are role-based
- commands are noun-verb

## bugs

- bugs are reported as failing tests
- iff code is faithful to spec, no failing tests ≡ no bugs
- a green suite whose code is not faithful to spec may as well be toilet paper
