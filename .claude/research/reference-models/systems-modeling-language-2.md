---
name: Systems Modeling Language v2.0
short-name: SysML v2
kind: systems-modelling-language
version: 2.0
formal-version: September 2025
notation: comparison abstraction
---

# systems modeling language v2

- OMG published SysML 2.0 as a formal specification dated September 2025 [status][about]
- SysML v2 is a metamodel extension of the Kernel Modeling Language [§6.1][language]
- a definition classifies and a usage denotes values in a context [§7.6][language]
- nested usages are features of their containing definition or usage [§7.6.1][language]

```text:types
Definition <: Classifier
Usage <: Feature
PartDefinition <: ItemDefinition
PartUsage <: ItemUsage
```

# composition

- a usage without the `ref` modifier is composite [§7.6.3][language]
- a composite value cannot outlive its featuring occurrence [§7.6.3][language]
- a composite value cannot simultaneously belong to another composite usage with a different featuring occurrence [§7.6.3][language]

```sysml:surface
part vehicle : Vehicle {
    part wheelAssembly[2] {
        part axle : Axle;
        part wheel : Wheel;
    }
}
```

# boundary and connection

- directed usages are referential [§7.6.3][language]
- a port usage identifies an interaction point on an occurrence [§7.11.3][language]
- a connection usage links two or more related features [§7.13.2][language]

```sysml:surface
part a : A { port p : ~P; }
part b : B { port q : P; }
connect a.p to b.q;
```

# observation and assurance

- a viewpoint definition frames stakeholder concerns about modelled information [§7.26][language]
- a view exposes model content, applies conditions, and renders a view artifact [§7.26][language]
- multiplicity, subsetting, and redefinition constrain usages [§§7.6.1, 7.6.3][language]

```text:surface
ViewArtifact = render(filter(expose(Model), ViewCondition), Rendering)
redefine(specific, general) -> subset(specific, general)
```

# refs

[about]: https://www.omg.org/spec/SysML/2.0/About-SysML
[language]: https://www.omg.org/spec/SysML/2.0/Language/PDF
