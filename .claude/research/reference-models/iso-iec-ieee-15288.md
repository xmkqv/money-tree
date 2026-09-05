---
name: Systems and software engineering — System life cycle processes
short-name: ISO/IEC/IEEE 15288
kind: system-life-cycle-process-standard
edition: 2023
notation: comparison abstraction
---

# system life cycle processes

- the standard defines a common framework of system life-cycle process descriptions [scope][standard]
- processes apply to systems of interest, their system elements, and systems of systems [scope][standard]
- processes may be applied iteratively, concurrently, and recursively [scope][standard]

```text:types
Process = <purpose, outcomes, activities, tasks>
ApplicationTarget = SystemOfInterest | SystemElement | SystemOfSystems
ProcessOutcome = observable result of successful ProcessPurpose
```

# boundary and recursion

- environment is the context of all influences on a system [§3.16][preview]
- an interface is a point where logical or physical system elements meet, act, or communicate [§3.19][preview]
- recursion repeats a process on successive system-element levels [§3.31][preview]

```text:surface
apply(ProcessSet, SystemOfInterest)
apply(ProcessSet, selected SystemElement) -> recursive application
iterate(ProcessSet, sameLevel) -> repeated application
```

# definition and realisation

- architecture concerns system concepts or properties in an environment and governing principles [§3.5][preview]
- design specifies system elements and relations sufficiently for compliant implementation [§3.13][preview]
- technical processes include architecture definition, design definition, implementation, and integration [clause 6.4][preview]

```text:surface
needs -> requirements -> architecture -> design
design -> implementation -> integration -> transition
```

# observation and assurance

- each process has stated outcomes that expose successful achievement of its purpose [§§3.29–3.30][preview]
- the standard supports conformance assessment for declared organisational and project process environments [introduction][preview]

```text:surface
assess(ProcessApplication) -> achievedOutcomeSet
conform(environment) iff declared processes satisfy applicable provisions
```

# refs

[standard]: https://www.iso.org/standard/81702.html
[preview]: https://cdn.standards.iteh.ai/samples/81702/5bd543dddf94457488c8cd8871897567/ISO-IEC-IEEE-15288-2023.pdf
