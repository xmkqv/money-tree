---
name: framework comparison
kind: comparison-matrix
notation: comparison abstraction
---

# framework comparison

- one row per framework document in this directory
- cell terms follow the linked document and its cited sources
- — marks a move a framework does not define

# structure

| framework | kind | system form | primitive |
|---|---|---|---|
| [RM-ODP foundations](./open-distributed-processing-foundations.md) | reference-model foundations | Object = <behaviour, state, interfaces> | object |
| [CESM](./composition-environment-structure-mechanism.md) | systemist model | CESM(s) = <C, E, S, M> | component |
| [BWW](./bunge-wand-weber.md) | information-system ontology | System = <composition, environment, structure> | coupled thing |
| [ISO/IEC/IEEE 42010](./iso-iec-ieee-42010.md) | architecture-description standard | ArchitectureDescription = ADElement+ | architecture description element |
| [UAF](./unified-architecture-framework.md) | enterprise-architecture framework | UAFGrid = Viewpoint x Aspect -> ViewSpecification? | UAF element |
| [ArchiMate](./archimate.md) | enterprise-architecture modelling language | Concept = Element \| Relationship | element |
| [Acme](./acme.md) | software-architecture description language | System = <components, connectors, attachments, properties> | component; connector |
| [SysML v2](./systems-modeling-language-2.md) | systems modelling language | part = composite PartUsage with nested Usage+ | part usage |
| [AADL](./architecture-analysis-design-language.md) | architecture description language | Implementation = <type, subcomponents, connections, flows, modes> | component |
| [OPM](./object-process-methodology.md) | conceptual modelling language and method | Model = <ObjectProcessDiagramSet, ObjectProcessLanguageText> | thing = object \| process |
| [IEC 81346-1](./iec-81346-1.md) | structuring and designation standard | Structure(aspect) = ObjectOccurrence + PartitiveRelation | object occurrence |
| [ISO/IEC/IEEE 15288](./iso-iec-ieee-15288.md) | system life-cycle process standard | Process = <purpose, outcomes, activities, tasks> | system element |
| [BIP](./behavior-interaction-priority.md) | component composition framework | CompoundComponent = <atomicComponents, connectors, priorities> | atomic component |
| [DEVS](./discrete-event-system-specification.md) | discrete-event modelling formalism | Coupled = <X, Y, D, {Model(d)}, EIC, EOC, IC, Select> | atomic model |
| [I/O automata](./input-output-automata.md) | asynchronous component model | Automaton = <signature, states, start, steps, partition> | automaton |
| [CSP](./communicating-sequential-processes.md) | process algebra | Process denoted by <traces, failures, divergences> | process |
| [structured cospans](./structured-cospans.md) | categorical open-system framework | StructuredCospan(a, b) = L(a) -> x <- L(b) | apex object |
| [FBS](./function-behaviour-structure.md) | design ontology | <F, Be, Bs, S, D> | design variable |

# boundary

| framework | boundary construct |
|---|---|
| RM-ODP | environment; interface over interactions |
| CESM | external item; component–environment bond |
| BWW | environment coupling |
| ISO/IEC/IEEE 42010 | entity environment; stakeholder concern |
| UAF | resource port toward the environment |
| ArchiMate | service exposing behaviour outside the system |
| Acme | port; role |
| SysML v2 | port usage |
| AADL | feature |
| OPM | in-zoom context boundary |
| IEC 81346-1 | aspect |
| ISO/IEC/IEEE 15288 | system-of-interest environment; interface |
| BIP | port |
| DEVS | input set X; output set Y |
| I/O automata | input and output actions |
| CSP | alphabet; shared events |
| structured cospans | feet L(a), L(b) |
| FBS | constraining system framework |

# composition

| framework | decomposition move | composition move |
|---|---|---|
| RM-ODP | specify an object as a composition | compose objects into an object at another abstraction level |
| CESM | refine a component as a system at a lower level | — |
| BWW | subsystem with subset composition and structure | coupling through the acts-on relation |
| ISO/IEC/IEEE 42010 | view into view components | correspondence between description elements |
| UAF | grid projection by viewpoint and aspect | resource role in a performer context; resource connector |
| ArchiMate | composition relation rendered by nesting | metamodel-valid relationships |
| Acme | representation of a component or connector | attachment of port to role |
| SysML v2 | nested composite usage | connection between port usages |
| AADL | implementation into subcomponents | connection; binding |
| OPM | unfolding; in-zooming | folding; out-zooming |
| IEC 81346-1 | partitive relation within one aspect | reference designation set across aspects |
| ISO/IEC/IEEE 15288 | recursive process application to system elements | integration |
| BIP | — | interaction and priority over ports |
| DEVS | coupled model into component models | external and internal coupling |
| I/O automata | — | compatible synchronized composition; hiding |
| CSP | hiding of internal events | synchronised parallel on shared events |
| structured cospans | cut along an interface | pushout serial composition; monoidal parallel composition |
| FBS | component framework constrained by the system framework | integration of design descriptions |

# observation and assurance

| framework | observable | preservation claim |
|---|---|---|
| RM-ODP | interaction trace | behavioural compatibility under environment criteria |
| CESM | CESM model at a time and level | mechanism explains change |
| BWW | state; event; history | good decomposition induces well-defined subsystem transforms |
| ISO/IEC/IEEE 42010 | view | conformance per target |
| UAF | view governed by a viewpoint | conformance from model interchange to view specification |
| ArchiMate | viewpoint-selected view | relationship-table validity |
| Acme | property; representation | style-constraint conformance |
| SysML v2 | rendered view artifact | composite lifetime and containment constraints |
| AADL | flow; system instance | instance resolution and property analysis |
| OPM | OPD and OPL of one model | equal meaning across modalities |
| IEC 81346-1 | reference designation | unambiguous object identification |
| ISO/IEC/IEEE 15288 | achieved outcome set | conformance of declared processes |
| BIP | global transition | maximal enabled interaction under priorities |
| DEVS | input and output events | closure under coupling |
| I/O automata | external behaviour | behaviour projection; implementation inclusion |
| CSP | traces; failures; divergences | refinement as set inclusion |
| structured cospans | interface feet | symmetric monoidal composition laws |
| FBS | derived behaviour; design description | evaluation of derived against expected behaviour |
