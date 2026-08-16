---
name: spec
refs:
    - [Lumibot](https://github.com/Lumiwealth/lumibot#quick-start)
    - [env](./.env.example)
---

# code

```sh
src/
    analysis/
        break-even-accuracy.py
        ...
    cli/
        __main__.py
    bot/
        strategies/
            shared.py # model, types, utils
            {name}.py
            ...
        config.py
        backtest.py
        broker.py
        trade.py
    ui/
        config.py
        app.py
        auth.py
```

# deploy

```sh
railway.toml
railway.web.toml
```

The worker starts `mt trade` with the `STRATEGY` variable.
The web service starts Uvicorn on `0.0.0.0:$PORT`.

Create a confidential OAuth application in the Railway workspace.
Set its callback to `https://<generated-domain>/auth/callback`.
Set the web variables from `.env.example` on `money-tree-web`.

The web service accepts only the two subjects in `ALLOWED_RAILWAY_SUBS`.
Do not set Alpaca credentials on the web service.
