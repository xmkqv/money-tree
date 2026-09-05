---
name: Software, systems and enterprise — Architecture description
short-name: ISO/IEC/IEEE 42010
kind: architecture-description-standard
edition: 2022
notation: comparison abstraction
---

# architecture description

- an architecture description is a work product used to express an architecture [§3.3][sample]
- architecture is distinct from the description that expresses it [scope][standard]
- an architecture description element is an identified or named part of the description [§3.4][sample]

```text:types
EntityOfInterest
ArchitectureDescription = ADElement+
ADElement = Stakeholder | Concern | Viewpoint | View | ViewComponent |
            ModelKind | Correspondence | OtherNamedPart
```

# boundary and concerns

- architecture concerns an entity in its environment [§3.2][sample]
- a concern is a matter of relevance or importance to a stakeholder [§3.10][sample]
- a viewpoint frames concerns and governs one or more views [§§3.8, 5.2.7][sample]

```text:surface
Stakeholder -> holds -> Concern
Viewpoint -> frames -> Concern+
Viewpoint -> governs -> View+
```

# projection and correspondence

- a view is an information part within an architecture description [§3.7][sample]
- a view component is a separable portion of one or more views [§3.19][sample]
- a correspondence records an identified relation between description elements [§§3.11, 5.2.11][sample]

```text:surface
View = ViewComponent+
modelBased(ViewComponent) -> governedBy(ModelKind)
correspondence : ADElement x ADElement
```

# assurance

- the standard specifies requirements for descriptions, frameworks, languages, viewpoints, and model kinds [scope][standard]
- conformance is assessed separately for each supported conformance target [clause 4][sample]

```text:surface
ConformanceTarget = ArchitectureDescription | DescriptionFramework |
                    DescriptionLanguage | Viewpoint | ModelKind
conform(target) iff target satisfies its stated requirements
```

# refs

[standard]: https://www.iso.org/standard/74393.html
[sample]: https://cdn.standards.iteh.ai/samples/74393/fc7b7f103d8446a4b87a3261e31370d3/ISO-IEC-IEEE-42010-2022.pdf
