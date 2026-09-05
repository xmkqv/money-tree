---
name: Open Distributed Processing — Reference Model: Foundations
short-name: RM-ODP Foundations
kind: reference-model-foundations
reference: ITU-T X.902 (10/2009) | ISO/IEC 10746-2:2010
notation: comparison abstraction
---

# open distributed processing foundations

- a system is something considered as a whole or as composed of parts [§6.5][x902]
- an entity is atomic only at a stated abstraction level [§6.4][x902]
- an object is a model of an entity characterised by behaviour and state [§8.1][x902]

```text:types
SourceTerm = Entity | System | Object | Environment | Action | Interface
Action = InternalAction | Interaction
ObjectView = <behaviour, state, interfaces>
```

# boundary

- an object's environment is the part of the model outside that object [§8.2][x902]
- an internal action excludes the environment [§8.3][x902]
- an interaction includes the environment and is therefore observable [§8.3][x902]

```text:surface
actions(o) = internalActions(o) + interactions(o)
interface(o) selects interactions(o) and constrains their occurrence
```

# composition

- object composition yields a new object at another abstraction level [§9.1][x902]
- behaviour composition yields a behaviour determined by its inputs and combination rule [§9.1][x902]
- decomposition specifies an object or behaviour as a composition [§9.3][x902]

```text:surface
composeObjects(Object+) -> Object
composeBehaviours(Behaviour+, CombinationRule) -> Behaviour
decompose(x) -> specification(x as composition)
```

# observation and assurance

- a trace is a finite interaction sequence and contains no internal action [§9.7][x902]
- behaviour determines its possible traces, but traces do not determine behaviour [§9.7][x902]
- behavioural compatibility is replacement that the environment cannot distinguish under stated criteria [§9.4][x902]

```text:surface
trace(o) = Interaction*
compatible(replacement, original, environment, criteria)
    iff environment cannot distinguish their behaviour under criteria
```

# refs

[x902]: https://www.itu.int/rec/dologin_pub.asp?lang=e&id=T-REC-X.902-200910-I!!PDF-E&type=items
