---
name: Input/Output Automata
short-name: I/O automata
kind: asynchronous-component-model
authors: Nancy A. Lynch, Mark R. Tuttle
reference: CWI Quarterly 2(3), 1989
notation: comparison abstraction
---

# input/output automata

- an I/O automaton has an action signature, states, start states, steps, and a local-action partition [§3.1][paper]
- the action signature separates input, output, and internal actions [§3.1][paper]
- every input action is enabled in every state [§3.1][paper]

```text:types
Automaton = <signature, states, start, steps, partition>
Signature = <inputs, outputs, internals>
Step : State x Action x State
```

# boundary and observation

- inputs and outputs are external actions visible to the environment [§3.1][paper]
- a behaviour is an execution schedule with internal actions removed [§3.1][paper]

```text:surface
external(A) = inputs(A) + outputs(A)
behaviour(execution) = restrict(schedule(execution), external(A))
```

# composition and hiding

- compatible automata have disjoint output actions and private internal actions [§3.2][paper]
- a shared action is performed simultaneously by every component that contains it [§3.2][paper]
- hiding converts selected actions to internal actions [§3.2][paper]

```text:surface
compose(Automaton+) -> Automaton
hide(ActionSet, A)
    remove ActionSet from external(A)
    add ActionSet to internals(A)
```

# assurance

- component behaviours project from every behaviour of their composition [propositions 1–3][paper]
- implementation is inclusion of finite external behaviours for equal external signatures [§3.4][paper]

```text:surface
implements(concrete, abstract) iff
    externalSignature(concrete) = externalSignature(abstract)
    and finiteBehaviours(concrete) subset finiteBehaviours(abstract)
```

# refs

[paper]: https://groups.csail.mit.edu/tds/papers/Lynch/CWI89.pdf
