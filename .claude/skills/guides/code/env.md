# env

- the environment is the sole declaration of variables
- the env mode determines the environment projection, i.e. loaded variables
- env mode ∈ { development, production }
- in mise, env mode depends on mise env via --env flag
- shared config is declared in mise.toml whereas mode-specific config is declared in config files

```invs
config ← mise.toml + mise.{mode}.toml
secrets ← .env.{mode}
```

```sh:command
mise --env production run ...
```

## tools

```toml:root:example
min_version = ...
monorepo_root = ...

[monorepo]
config_roots = ["lib/db", "lib/e2e"]

[tools]
bun = ...
"npm:wrangler" = ...
...
```

## config

- any variable is assigned exactly once
- variables can be namespaced like {NAMESPACE}__{NAME}

```mise.toml/mise.{mode}.toml
[env]
{NAME} = ...
...

{NAME} = '' # empty value declares an unassigned variable, i.e. like a .env.example declaration

_.file = { path = ".env.{ENV_MODE}", redact = true } # env mode dependent secret loading
```

## tasks

- a module declares its own tasks
- task name ∈ { setup, build, serve, stop, check, test, deploy }
- the root declares `test` as its sole validation task
- local and continuous runners invoke the root test
- omit descriptions
- there is no separate 'mise-tasks' directory, runners are inlined to the task file always
- runners delegate environment checks to consumers, i.e. runners do not check environment

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

# refs

[file tasks]: https://mise.jdx.dev/tasks/file-tasks.html
[secrets]: https://mise.jdx.dev/environments/secrets/
[environments]: https://mise.jdx.dev/configuration/environments.html
