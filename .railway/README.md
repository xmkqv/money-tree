# Railway configuration

The production project is defined in `railway.ts`.

```sh
mise --env production run deploy
```

The task installs the infrastructure package, previews the plan, and asks before
applying it. Production values come from `mise.production.toml` and the ignored
`.env.production` loaded after it.
