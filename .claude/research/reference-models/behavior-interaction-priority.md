---
name: Behavior–Interaction–Priority
short-name: BIP
kind: component-composition-framework
authors: Ananda Basu, Marius Bozga, Joseph Sifakis
reference: Dagstuhl Seminar Proceedings 08331, 2008
notation: comparison abstraction
---

# behavior–interaction–priority

- Behavior is the local transition layer [§2.1][paper]
- Interaction coordinates transitions through component ports [§2.2][paper]
- Priority selects among enabled interactions [§2.3][paper]

```text:types
AtomicComponent = <ports, controlStates, variables, transitions>
Transition = <source, port, guard, update, target>
CompoundComponent = <atomicComponents, connectors, priorities>
```

# boundary and interaction

- ports are action names used for synchronisation [§2.1][paper]
- a connector defines interaction patterns over ports of distinct atomic components [§2.2][paper]

```text:surface
Interaction = Port+
enabled(interaction, state) iff
    connectorGuard(interaction) and every local guard holds
```

# composition

- the compound state is the Cartesian product of atomic control states [§3.1][paper]
- an executed interaction advances only the atomic components that participate [§3.1][paper]

```text:surface
GlobalState = product(AtomicControlState)
execute(interaction)
    run connector update
    run participating local updates
    keep every other local state
```

# observation and assurance

- the execution engine computes enabled interactions and removes lower-priority choices [§3.1][paper]
- one maximal enabled interaction is executed at each engine choice [§3.1][paper]

```text:surface
candidates = enabledInteractions(GlobalState)
maximal = applyPriorities(candidates, GlobalState)
choose(maximal) -> GlobalTransition
```

# refs

[paper]: https://doi.org/10.4230/DagSemProc.08331.5
