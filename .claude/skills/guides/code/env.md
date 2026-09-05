# env

[environments](https://mise.jdx.dev/configuration/environments.html)

- the environment is the sole declaration of variables

```invs
configuration = mise.{mode}.toml
secrets = .env.{mode}
```

## mode = development | production

- the development mode is the shell default
- the production mode is activated per invocation
- the root checks that a mode is selected, before any consumer runs

```sh:rc
export MISE_ENV=development
```

```sh:command
mise --env production run //:deploy HEAD
```

```toml:root
[vars]
mode = "{% if mise_env %}{{ mise_env | join(sep='') }}{% else %}{{ throw(message='no environment selected: rerun with --env development or --env production') }}{% endif %}"
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

## tasks

[file tasks](https://mise.jdx.dev/tasks/file-tasks.html)

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
depends = ["//lib/db:reset", ":start"]
run = "bun run test"
```

## configuration

- a mode file is complete, i.e. no mode file is a base for another
- a variable is assigned exactly once

```toml:development
[env]
SITE_URL = "http://127.0.0.1:5173"
CLERK_PUBLISHABLE_KEY = "pk_test_…"
```

```toml:production
[env]
SITE_URL = "https://…"
CLERK_PUBLISHABLE_KEY = "pk_live_…"
CLOUDFLARE_ACCOUNT_ID = "…"
```

## secrets

- a mode file declares each secret it consumes with an empty value, grouped by concern
- a mode file loads its secrets last, i.e. the secrets file overrides the declarations
- production secrets extend development secrets
- no tracked file is named `.env*`
- [secrets](https://mise.jdx.dev/environments/secrets/)

```toml:production:example
[env]
CLERK_SECRET_KEY = ""
## deployment
CLOUDFLARE_API_TOKEN = ""
## release
APPLE_API_KEY_ID = ""

_.file = { path = ".env.production", redact = true }
```
