---
name: Acme architecture description language
short-name: Acme
kind: software-architecture-description-language
authors: David Garlan, Robert T. Monroe, David Wile
reference: CASCON 1997
notation: comparison abstraction
---

# acme

- Acme defines systems, components, connectors, ports, roles, representations, and representation maps [design elements][overview]
- a system is a configuration of components and connectors [design elements][overview]
- components and connectors are the principal structural units [design elements][overview]

```text:types
System = <components, connectors, attachments, properties>
Component = <ports, properties, representations>
Connector = <roles, properties, representations>
```

# boundary and composition

- ports form component interfaces and roles form connector interfaces [design elements][overview]
- an attachment joins a component port to a connector role [simple system][overview]

```text:surface
Attachment : Port x Role

+--------+     +-----------+     +--------+
| client |---->| connector |---->| server |
+--------+     +-----------+     +--------+
```

# decomposition

- a component or connector may have one or more lower-level representations [representations][overview]
- a representation map associates an external interface with the representation's internal interface [representations][overview]

```text:surface
Representation = System
RepMap = ExternalPort x InternalPort | ExternalRole x InternalRole
```

# observation and assurance

- properties carry non-structural information in externally defined sublanguages [language features][overview]
- Acme maps structural descriptions to relations and constraints without fixing computational semantics [open semantics][overview]

```text:surface
prescription(System) -> Predicate
check(System, StyleConstraints) -> conformant | violation
```

# refs

[overview]: https://www.cs.cmu.edu/~acme/docs/language_overview.html
