# Initial build intent

## Outcome

The initial build declares one generic interface for each layer. Every interface accepts a type
discriminator that selects a named implementation module without changing the interface.
The initial build resolves and runs every implementation locally.

## Layer system

- Data, loaders, transformers, models, deciders, and traders each own one generic adapter
- Every generic adapter accepts a layer-local type discriminator plus its payload input
- Every type discriminator names one implementation type within one layer
- Every implementation type belongs to one direct child module of that layer
- The layer root resolves the discriminator and delegates to the selected module
- Consumers keep the same input and output types when the selected module changes

The research documents remain catalogs of possible implementation modules. Selecting a product or
library means adding a named module under the appropriate layer and assigning its discriminator.
Discriminator types are nominal; concrete values are introduced with implementation modules.

## Module switching

```text
type discriminator
  -> layer root
  -> named child module
  -> generic adapter output
```

Changing the discriminator changes the implementation behind one layer. It does not change the
layer interface, adjacent layers, or system composition.

## Execution boundary

- Every initial implementation executes in the local process
- A type discriminator selects an implementation module, not an execution location
- Execution location remains hidden behind the generic layer interface
- A future implementation may dispatch to a server without changing its interface
- Server transport, discovery, deployment, and orchestration remain outside the initial build

## Deliverables

- Six generic layer adapters
- Six layer-local type discriminator contracts
- Six layer-local discriminator resolvers
- One stable input and output boundary for every generic adapter
- A direct mapping from each discriminator to one child implementation module

## Acceptance

- Every layer exports exactly one generic adapter
- Every generic adapter accepts exactly one layer-local type discriminator
- Every discriminator resolves to exactly one implementation type in its own layer
- An unknown discriminator is invalid
- Changing a valid discriminator changes only the selected implementation
- Adapter inputs and outputs remain invariant when implementations switch
- Every selected implementation executes locally in the initial build
- No external product or infrastructure dependency is part of the initial system
- The specification passes the repository conventions

## Explicit deferrals

- Testing discriminator resolution and adapter invariance
- Selecting or integrating any cataloged provider, framework, model, optimizer, or broker
- Defining server transport, discovery, deployment, or orchestration
- Choosing persistence, streaming, orchestration, training, evaluation, or execution infrastructure
- Building a concrete research, backtest, paper-trading, or live-trading composition
