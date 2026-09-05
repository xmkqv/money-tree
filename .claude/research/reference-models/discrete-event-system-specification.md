---
name: Discrete Event System Specification
short-name: DEVS
kind: discrete-event-modelling-formalism
authors: Bernard P. Zeigler, Herbert Praehofer, Tag Gon Kim
notation: comparison abstraction
---

# discrete event system specification

- an atomic model supplies state and event-transition behaviour [atomic models][formalism]
- a coupled model supplies component and coupling structure [coupled models][formalism]
- both forms expose input and output event sets [formalism][formalism]

```text:types
Atomic = <X, Y, S, deltaExternal, deltaInternal, output, timeAdvance>
TotalState = <state, elapsedTime>
deltaExternal : TotalState x X -> S
deltaInternal : S -> S
output : S -> Y
```

# boundary

- X contains accepted input events and Y contains produced output events [atomic models][formalism]
- external coupling routes coupled-model inputs to component inputs [coupled models][formalism]
- external output coupling routes component outputs to coupled-model outputs [coupled models][formalism]

```text:types
EIC : CoupledInput x ComponentInput
EOC : ComponentOutput x CoupledOutput
IC  : ComponentOutput x ComponentInput
```

# composition

- a coupled model contains atomic or coupled component models [coupled models][formalism]
- internal coupling routes output events between component models [coupled models][formalism]

```text:types
Coupled = <X, Y, D, {Model(d)}, EIC, EOC, IC, Select>
Model(d) = Atomic | Coupled
```

# observation and assurance

- coupled-model state includes the total state of every component [resultant][formalism]
- closure under coupling represents coupled behaviour using atomic-model conventions [resultant][formalism]

```text:surface
resultant(Coupled) -> Atomic
state(resultant) = product(ComponentTotalState)
timeAdvance(resultant) = minimum remaining component time
```

# refs

[formalism]: https://cell-devs.sce.carleton.ca/publications/2013/GWK13/DEVSintro.pdf
