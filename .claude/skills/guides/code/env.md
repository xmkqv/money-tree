# env

```invs
environment ⊇ declarations(variables)
mode ∈ { development, production }
loaded variables = environment[mode]
mise.toml + mise.{mode}.toml → config
.env.{mode} → secrets
```

```sh:command
mise --env production run …
```

## tools

```toml:root:example
min_version = …
monorepo_root = …

[monorepo]
config_roots = ["lib/db", "lib/e2e"]

[tools]
bun = …
"npm:wrangler" = …
…
```

## config

- ∀ variable: count(assignments(variable)) ≤ 1
- variables can be namespaced like {NAMESPACE}__{NAME}

```mise.toml/mise.{mode}.toml
[env]
{NAME} = …
…

{NAME} = '' # unassigned

_.file = { path = ".env.{ENV_MODE}", redact = true }
```

## tasks

- a module declares its own tasks
- task name ∈ { setup, build, serve, stop, check, test, deploy }
- local and continuous runners invoke the root test
- omit descriptions
- runners are inlined in task declarations
- runners delegate environment checks to consumers

```toml:root
[tasks.test]
run = [
  { tasks = ["//lib/db:check", "//lib/e2e:check"] },
  { tasks = ["//lib/db:test", "//lib/e2e:test"] },
]
```

```toml:module
[tasks.test]
depends = ["//lib/db:build", ":build"]
run = "bun run test"
```

## refs

- [file tasks](https://mise.jdx.dev/tasks/file-tasks.html)
- [secrets](https://mise.jdx.dev/environments/secrets/)
- [environments](https://mise.jdx.dev/configuration/environments.html)
