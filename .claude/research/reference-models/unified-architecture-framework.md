---
name: Unified Architecture Framework
short-name: UAF
kind: enterprise-architecture-framework
version: 1.3
adoption: April 2026
notation: comparison abstraction
---

# unified architecture framework

- UAF 1.3 has normative Domain Metamodel and UAF Modeling Language specifications [specification documents][about]
- the Domain Metamodel is based on a simplified IDEAS ontology [§6.4][dmm]
- an ArchitecturalDescription is a work product that expresses an architecture of a system of interest [§9.1.2][dmm]

```text:types
UAFElement
Architecture = OperationalArchitecture | ServiceArchitecture |
               ResourceArchitecture
ArchitecturalDescription -> expresses -> Architecture
```

# projection

- the UAF Grid places viewpoints in rows and aspects in columns [§7][dmm]
- each populated grid cell specifies a view specification [§7][dmm]
- a View is governed by one Viewpoint and communicates an aspect of an architecture [§9.1.2][dmm]

```text:surface
UAFGrid = Viewpoint x Aspect -> optional ViewSpecification
Viewpoint -> frames -> Concern+
Viewpoint -> governs -> View+
```

# resources and boundary

- a ResourceRole is a ResourcePerformer used in another ResourcePerformer's context [§9.1.7][dmm]
- a ResourcePort is an outside-environment interaction point [§9.1.7][dmm]
- a ResourceConnector is an exchange channel between two ResourceRoles [§9.1.7][dmm]

```text:types
ResourcePerformer
ResourcePort : interactionPoint(ResourcePerformer, Environment)
ResourceConnector : ResourceRole x ResourceRole
ResourceExchange = flow(Data | Person | Material | Energy)
ResourceMethod -> specifiedBy -> Function
```

# assurance

- conceptual-syntax conformance requires consistency with Domain Metamodel concepts, relationships, and constraints [clause 2][dmm]
- model-interchange conformance requires import and export of conformant XMI for valid UAFML models [clause 2][dmm]

```text:surface
Conformance = ViewSpecification | ConceptualSyntax | FormalSyntax |
              ModelInterchange
ModelInterchange -> FormalSyntax -> ConceptualSyntax -> ViewSpecification
```

# refs

[about]: https://www.omg.org/spec/UAF/1.3/About-UAF
[dmm]: https://www.omg.org/spec/UAF/1.3/DMM/PDF
