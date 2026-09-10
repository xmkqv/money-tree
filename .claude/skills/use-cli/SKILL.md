---
name: use-cli
description: only-if-asked
---
# cli

## rules

- idiomatic typed typescript
- skills.guides(spec, code)
- completions install with an explicit shell, not autodetection
- argument types derive from the parser, not a second declaration
- validation lives in the grammar, not the handler
- a destructive command takes a required flag
- environment reads are lazy so completion runs without them

```text
{name}/
    main.ts
    package.json
    tsconfig.json
    …
```

```ts
import { object, or } from '@optique/core/constructs'
import { message } from '@optique/core/message'
import { command, constant } from '@optique/core/primitives'
import { run } from '@optique/run'

const cli = or(
  command(
    '{noun}',
    command('{verb}', object({ action: constant('{noun}.{verb}') }), {
      brief: message`{Verb} the {noun}.`
    }),
    { brief: message`The {noun}.` }
  )
)

const argv = Bun.argv.slice(2)

const cmd = run(cli, {
  args: argv.length ? argv : ['--help'],
  programName: '{name}',
  help: 'both',
  completion: { command: true }
})

switch (cmd.action) {
  case '{noun}.{verb}':
    await {verb}{Noun}()
    break
}
```

```md:form:clispec
{noun} {verb}(…) → {return}
{another-noun} {verb}(…) → {return}
…
```

cli(name, install?, completions?)
  log clispec`{infer(context or AskUserQuestion())}`
  bun init {name} && cd {name} && bun add @optique/core @optique/run
  implement the design
  if install, bun link
  if completions, {name} completion {shell} > {dir on fpath}/_{name}
