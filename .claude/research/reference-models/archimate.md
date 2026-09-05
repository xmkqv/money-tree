---
name: ArchiMate Specification
short-name: ArchiMate
kind: enterprise-architecture-modelling-language
version: 3.2
release: October 2022
notation: comparison abstraction
---

# archimate

- ArchiMate is an open enterprise-architecture modelling language [overview][spec]
- its core distinguishes active structure, behaviour, and passive structure [§3.4][spec]
- business, application, and technology are the three core layers [§3.4][spec]

```text:types
Concept = Element | Relationship
CoreAspect = ActiveStructure | Behaviour | PassiveStructure
CoreLayer = Business | Application | Technology
```

# structure and behaviour

- active structure is assigned to behaviour [structure and behaviour][guide]
- behaviour accesses passive structure [passive structure][guide]
- a service models behaviour exposed outside the system [external behaviour][guide]

```text:surface
ActiveStructure -> assignment -> Behaviour
Behaviour -> access -> PassiveStructure
Behaviour -> realisation -> Service
```

# decomposition and views

- composition relates a whole to constituents and can be rendered by nesting [composition][guide]
- a view selects model content for stakeholder concerns under a viewpoint [§14][spec]

```text:surface
composition : Element x Element
View = select(Model, Viewpoint, StakeholderConcern+)
```

# assurance

- the normative relationship tables define permitted element–relationship–element combinations [appendix B][spec]
- derivation rules distinguish relationships that are certain from those that are only potential [appendix B][spec]

```text:surface
valid(source, relationship, target) iff
    combination appears in the normative relationship tables
```

# refs

[spec]: https://pubs.opengroup.org/architecture/archimate32-doc/
[guide]: https://archimate-community.pages.opengroup.org/workgroups/archimate-101/
