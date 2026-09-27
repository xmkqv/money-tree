# env

- environment ⊇ declarations(variables)
- mode ∈ { development, production }
- loaded variables = environment[mode]
- mise.toml + mise.{mode}.toml → config
- .env.{mode} → secrets

```sh:command
mise --env production run …
```

## tools

```toml:root
min_version = …
monorepo_root = …

[monorepo]
config_roots = ["lib/{module}", …]

[tools]
bun = …
"npm:wrangler" = …
…
```

## config

- ∀ variable: count(assignments(variable)) ≤ 1
- variables can be namespaced like {NAMESPACE}__{NAME}

```toml:config
[env]
{NAME} = …
…

{NAME} = '' # unassigned

_.file = { path = ".env.{ENV_MODE}", redact = true }
```

## tasks

- a module declares its own tasks
- task name ∈ { reset, build, serve, stop, check, test, deploy }
- local and continuous runners invoke the root test
- a task declaration has no description
- runners are inlined in task declarations
- runners delegate environment checks to consumers

```toml:root
[tasks.test]
run = [
  { tasks = ["//lib/{module}:check", …] },
  { tasks = ["//lib/{module}:test", …] },
]
```

```toml:module
[tasks.test]
depends = ["//lib/{module}:build", ":build"]
run = "bun run test"
```

## refs

- [file tasks](https://mise.jdx.dev/tasks/file-tasks.html)
- [secrets](https://mise.jdx.dev/environments/secrets/)
- [environments](https://mise.jdx.dev/configuration/environments.html)
