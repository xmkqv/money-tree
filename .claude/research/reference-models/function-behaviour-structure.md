---
name: Function–Behaviour–Structure framework
short-name: FBS
kind: design-ontology
authors: John S. Gero, Udo Kannengiesser
reference: Design Studies 25(4), 2004
notation: comparison abstraction
---

# function–behaviour–structure

- function variables describe what the design object is for [§2][fbs]
- behaviour variables describe attributes derived or expected from structure [§2][fbs]
- structure variables describe components and their relationships [§2][fbs]

```text:types
F  = FunctionVariable*
Be = ExpectedBehaviourVariable*
Bs = StructureDerivedBehaviourVariable*
S  = StructureVariable*
D  = DesignDescription
```

# derivation

- formulation transforms function into expected behaviour [§2][fbs]
- synthesis produces a structure intended to exhibit the expected behaviour [§2][fbs]
- analysis derives actual behaviour from the structure [§2][fbs]
- evaluation compares derived behaviour with expected behaviour [§2][fbs]
- documentation produces the design description from the structure [§2][fbs]

```text:surface
formulation   : F -> Be
synthesis     : Be -> S
analysis      : S -> Bs
evaluation    : Bs <-> Be
documentation : S -> D
```

# reformulation

- structure reformulation changes the structure state space [§2][fbs]
- behaviour reformulation changes the expected-behaviour state space [§2][fbs]
- function reformulation changes the function state space by way of expected behaviour [§2][fbs]

```text:surface
structureReformulation : S -> S'
behaviourReformulation : S -> Be'
functionReformulation  : S -> F' via Be'

inv:Bs incompatible with Be -> reformulate
```

# composition

- each model in a composition carries its own FBS framework constrained by the frameworks of the other models [abstract][composition]
- the connected frameworks support modular design of one object [abstract][composition]
- component design descriptions integrate into the system design description [§3.3][composition]

```text:surface
FBS(component) constrained by FBS(system)
S(component) subset S(system)
integrate(D(component)+) -> D(system)

inv:reformulation blocked in a component -> reformulate(system)
```

# refs

[fbs]: https://doi.org/10.1016/j.destud.2003.10.010
[composition]: https://arxiv.org/abs/1504.00542
