# sketch

- a sketch renders one subject
- content ∈ label, sketch glyph
- label.words ⊆ context.words
- sketch.w ≤ 72
- sketch.h ≤ 2 * sketch.w
- whitespace ∈ tab, newline
- strokes are never broken or misaligned

## architecture

- an architecture outlines layers and their relationships
- a relationship renders as one arrow from source to target

```sketch:form:architecture
┌─────────┐   ┌─────────┐
│ {layer} ├──→│ {layer} │
└────┬────┘   └─────────┘
     │
     ↓
┌─────────┐
│ {layer} │
└─────────┘
```

## protocol

- a protocol renders as a message sequence chart
- a msg can be a named type, status, or other canonical payload
- an actor is a layer
- actors share one specificity
- count(actors) ≤ 3

```sketch:form:protocol
{actor}       {actor}       {actor}
   │             │             │
   ├──{msg}─────→│             │
   │             ├──{msg}─────→│
   │             │←──{msg}─────┤
   │←──{msg}─────┤             │
   │             │             │
```
