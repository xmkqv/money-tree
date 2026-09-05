---
name: Architecture Analysis & Design Language
short-name: AADL
kind: architecture-description-language
edition: SAE AS5506D
revision: April 2022
notation: comparison abstraction
---

# architecture analysis & design language

- AADL models software and execution-platform architectures of real-time systems [scope][standard]
- a component type specifies a component's visible functional and behavioural interface [annex A][preview]
- a component implementation describes internal structure and may realise one component type [§4.4][preview]

```text:types
ComponentClassifier = ComponentType | ComponentImplementation
ComponentType = <features, flows, properties, modes>
ComponentImplementation = <type, subcomponents, calls, connections,
                           flows, modes, properties>
```

# decomposition

- a component implementation can declare subcomponents and their connections [§4.4][preview]
- one component type can have multiple component implementations [§4.4][preview]

```aadl:surface
system controller
features
    input  : in data port sample;
    output : out data port command;
end controller;

system implementation controller.basic
subcomponents
    control : process control.impl;
end controller.basic;
```

# boundary and configuration

- features form the externally visible interaction points of a component type [§8][preview]
- modes support mode-specific configurations and property values [§12][preview]
- application software can be bound to execution-platform components [§13][preview]

```text:surface
Feature = Port | Access | Parameter | FeatureGroup
Configuration(instance, mode) = active subcomponents + active connections
bind(Thread | Process, Processor)
```

# observation and assurance

- flows describe paths through components and connections [§10][preview]
- a system instance resolves the declarative model into an operational configuration [§13][preview]

```text:surface
Flow = Source | Sink | Path | EndToEnd
instantiate(ComponentImplementation, Mode) -> SystemInstance
analyse(SystemInstance, PropertySet) -> Result
```

# refs

[standard]: https://saemobilus.sae.org/standards/as5506d-architecture-analysis-design-language-aadl
[preview]: https://www.normsplash.com/Samples/SAE/111867218/SAE-AS-5506D-2022-en.pdf
