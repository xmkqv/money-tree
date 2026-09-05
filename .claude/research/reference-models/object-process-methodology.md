---
name: Automation systems and integration — Object-Process Methodology
short-name: OPM
kind: conceptual-modelling-language-and-method
edition: ISO 19450:2024
notation: comparison abstraction
---

# object-process methodology

- ISO 19450 specifies OPM as a modelling paradigm and language for conceptual models [scope][standard]
- OPM specifies a single function–structure–behaviour model [§3.44][preview]
- objects and processes are the two kinds of thing [§6.2.3][preview]
- a process is a transformation of one or more objects in the system [§3.59][preview]

```text:types
Thing = Object | Process
Link = StructuralLink | ProceduralLink
Model = <ObjectProcessDiagramSet, ObjectProcessLanguageText>
```

# structure and behaviour

- a link expresses a structural or a procedural relation between things [§3.37][preview]
- a procedural relation connects an object or object state with a process [§3.58][preview]
- transforming links express consumption, result, or effect [§9.1][preview]
- enabling links express agent or instrument participation [§9.2][preview]

```text:types
FundamentalStructuralRelation = AggregationParticipation |
                                ExhibitionCharacterization |
                                GeneralizationSpecialization |
                                ClassificationInstantiation
TransformingLink = Consumption | Result | Effect
EnablingLink = Agent | Instrument
```

# refinement

- folding hides the refineables of a thing and unfolding exposes them [§3.23][preview]
- in-zooming orders constituent objects spatially and constituent processes temporally [§§3.35–3.36][preview]
- out-zooming reverses the corresponding in-zooming [§§3.49–3.50][preview]

```text:surface
unfold(Thing) -> refineables
inZoom(Object) -> constituent objects with spatial order
inZoom(Process) -> constituent processes with temporal partial order
fold and outZoom reverse the corresponding exposure
```

# observation and assurance

- an Object-Process Diagram and its Object-Process Language text represent the same model [§§3.42–3.44][preview]
- the textual modality retains the constraints of the graphical modality [introduction][preview]

```text:surface
OPD(Model) <-> OPL(Model)
meaning(OPD(Model)) = meaning(OPL(Model))
```

# refs

[standard]: https://www.iso.org/standard/84612.html
[preview]: https://cdn.standards.iteh.ai/samples/84612/327a043263ba4439971f660cdeb993eb/ISO-PRF-19450.pdf
