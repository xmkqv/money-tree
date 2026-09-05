---
name: Structured cospans
kind: categorical-open-system-framework
authors: John C. Baez, Kenny Courser
reference: Theory and Applications of Categories 35(48), 2020
notation: comparison abstraction
---

# structured cospans

- a structured cospan has the form L(a) -> x <- L(b) [§2][paper]
- the objects a and b specify interfaces while x specifies the open system [§2][paper]
- L maps interface objects from A into the system category X [§2][paper]

```text:types
L : A -> X
StructuredCospan(a, b) = L(a) -> x <- L(b)
Interface = Object(A)
OpenSystem = Object(X)
```

# serial composition

- serial composition forms a pushout over the shared interface [§2][paper]
- the identity at a is L(a) -> L(a) <- L(a) [§2][paper]

```text:surface
L(a) -> x <- L(b)    L(b) -> y <- L(c)

compose(x, y) = L(a) -> x +[L(b)] y <- L(c)
identity(a) = L(a) -> L(a) <- L(a)
```

# parallel composition

- the monoidal product places structured cospans in parallel via coproduct [§3][paper]

```text:surface
(x : a -> b) tensor (y : c -> d) : a+c -> b+d
apex(x tensor y) = x + y
```

# assurance

- finite colimits in A and X with L a left adjoint yield a symmetric monoidal category of isomorphism classes [corollary 3.11][paper]
- the construction also yields a symmetric monoidal double category whose horizontal cells are structured cospans [theorem 3.9][paper]

```text:surface
finiteColimits(A, X) and leftAdjoint(L)
    -> symmetricMonoidalCategory(IsomorphismClass(StructuredCospan))
    -> hypergraphCategory
```

# refs

[paper]: https://arxiv.org/abs/1911.04630
