---
name: Bunge–Wand–Weber ontological model
short-name: BWW
kind: information-system-ontology
authors: Yair Wand, Ron Weber
reference: IEEE TSE 16(11), 1990
notation: comparison abstraction
---

# bunge–wand–weber

- a thing is described by state variables selected for a modelling purpose [§III-A][paper]
- an event is an ordered pair of states [definition 4][paper]
- a history records a thing's states over time [definition 7][paper]

```text:types
Thing
State = StateVariableValue*
Event = <State, State>
History = Time x State
```

# coupling and boundary

- one thing acts on another when the latter's history depends on the former [definition 8][paper]
- two things are coupled when either acts on the other [definition 9][paper]
- the environment contains outside things that act on a component or are acted on by one [definition 11][paper]

```text:surface
acts(x, y) iff history(y given x) != history(y)
coupled(x, y) iff acts(x, y) or acts(y, x)
```

# system and decomposition

- a system is a set of things connected by its coupling relation [definition 10][paper]
- system structure contains internal and environment couplings [definition 11][paper]
- a subsystem has subset composition and structure, with omitted system things available to its environment [definition 12][paper]

```text:surface
System = <composition, environment, structure>
subsystem(x, s) requires
    composition(x) subset composition(s)
    structure(x) subset structure(s)
```

# observation and assurance

- system events must induce an event in at least one subsystem [lemma 3][paper]
- decomposition quality is relative to a selected system transformation [definition 31][paper]
- a good decomposition induces a well-defined internal transformation in every subsystem [definition 31][paper]

```text:surface
goodDecomposition(D, transform) iff
    every subsystem in D receives one wellDefined induced transform
```

# refs

[paper]: https://doi.org/10.1109/32.60316
