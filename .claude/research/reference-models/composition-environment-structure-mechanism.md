---
name: Composition–Environment–Structure–Mechanism
short-name: CESM
kind: systemist-model
authors: Mario Bunge
reference: How Does It Work? (2004)
notation: comparison abstraction
---

# composition–environment–structure–mechanism

- a concrete system can be modelled by composition, environment, structure, and mechanism [pp. 188–189][bunge]
- composition lists the system's components [pp. 188–189][bunge]
- a mechanism is a process in a concrete system that makes it what it is [abstract][bunge]

```text:types
CESM(s) = <C(s), E(s), S(s), M(s)>
C = ComponentSet
E = ExternalItemSet
S = BondSet
M = CharacteristicProcessSet
```

# boundary

- the environment contains items outside the system that act on it or are acted on by it [pp. 188–189][bunge]
- structure includes bonds among components and bonds between components and environment [pp. 188–189][bunge]

```text:surface
E(s) = {x | x notin C(s) and interacts(x, s)}
S(s) subset (C(s) x C(s)) + (C(s) x E(s)) + (E(s) x C(s))
```

# decomposition

- the CESM model fixes a system, a time, and an abstraction level [pp. 188–189][bunge]
- a component can itself be considered as a system at another selected level [pp. 188–189][bunge]

```text:surface
describe(s, time, level) -> CESM(s)
refineComponent(c, time, lowerLevel) -> CESM(c)
```

# observation and explanation

- the CESM description is a model of a system rather than the system itself [p. 188][bunge]
- mechanism supplies the explanatory coordinate of the model [pp. 182–183, 188–189][bunge]

```text:surface
observe(s, time, level) -> <C, E, S, M>
explain(change) -> characteristicProcess in M(s)
```

# refs

[bunge]: https://doi.org/10.1177/0048393103262550
