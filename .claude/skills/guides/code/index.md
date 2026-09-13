# code

- code = ( src, tests )
- code reads naturally and has no comments
- code is written in a functional style
- code fails fast through early checks
- src ∌ functions used only by tests

guides: env,tests,css,nu,py,rs,ts

router(keys=infer())
  keys.each(skills.guides.code.{key})

## code volume

- Δ code volume = (Δ count(non-whitespace chars), Δ count(non-whitespace lines))

## packages

- widest and latest version ranges

## modules

- generally, order module concerns: imports, types, constants, surface, private
- imports are relative when no upward traversal is needed; otherwise absolute

## names

- code names are monotonic over asd-ste100 and spec
- code identifiers compose entity tkeys with idiomatic casing and separators

### nouns

- types, entities, values, and nullary accessors are compact noun phrases
  - implementation qualifiers follow the role
- entity tables are singular, collections are plural
  - primary keys are bare, foreign keys are qualified
- value names expose their meaning
  - booleans are predicates
  - instants end with `_at`; dates end with `_on`
  - quantities end with a unit suffix, e.g. `*_ms`
  - bounded constants end with their bounds

### verbs

- side effects are verb phrases
  - `get` retrieves by key
  - `find` searches
  - mutations and transitions use explicit verbs
- related operations preserve the same entity tkeys
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
- passing(tests) ↛ faithful(code, spec)
