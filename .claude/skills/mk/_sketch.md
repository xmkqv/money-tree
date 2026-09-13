# sketch

- a sketch renders one subject
- content ∈ label, sketch glyph
- label.words ⊆ context.words
- sketch.w ≤ 72
- sketch.h ≤ 2 * sketch.w
- whitespace ∈ { space, newline }
- strokes are never broken or misaligned

## architecture

- an architecture outlines layers and their relationships
- a relationship renders as one arrow from source to target

```sketch:form:architecture
┌───────┐   ┌───────┐
│{layer}├──→│{layer}│
└───┬───┘   └───────┘
    ↓
┌───────┐
│{layer}│
└───────┘
```

## protocol

- a protocol renders as a message sequence chart
- a msg can be a named type, status, or other canonical payload
- an actor is a layer
- actors share one specificity
- count(actors) ≤ 3

```sketch:form:protocol
{actor}         {actor}         {actor}
│               │               │
├──{msg}───────→│               │
│               ├──{msg}───────→│
│               │←──{msg}───────┤
│←──{msg}───────┤               │
│               │               │
```

## tree

- refs are entity tkeys as inline markdown references, i.e. `[{tkey}]`, to entities outside an entities fov
- a node is an entity
- code tree → dir, files, and stubs
  - a stub is a single spec line, e.g. the signature of a function
- spec tree → layers and entities

```md:form:tree
{entity} {deps?}
├── {entity} {deps?}
│   ├ {entity} {deps?}
│   └ {entity} {deps?}
└── {entity} {deps?}
    └── {entity} {deps?}
        ├ {entity} {deps?}
        …
```
