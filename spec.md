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
            noop.py # deployment-safe strategy that submits no orders
            {name}.py # future trading strategy
            ...
        config.py
        backtest.py
        broker.py
        export.py
        trade.py
    ui/
        assets/
            dashboard.v1.html
            dashboard.v1.css
            dashboard.v1.js
        alpaca.py
        dashboard.py
        config.py
        app.py
        auth.py
```

# deploy

```sh
railway.toml
railway.web.toml
```

The bot starts `mt trade` with the `STRATEGY` variable.
The web service starts one Uvicorn worker on all interfaces and uses one Railway replica.

Create a confidential Railway OAuth application with the callback `https://<generated-domain>/auth/callback`.
Set the web variables from `.env.example` on `money-tree-web`.

Give the web service a separate paper Alpaca credential for named GET requests.

The dashboard reads each URL separately. The browser stores each response for its declared lifetime. FastAPI keeps no broker cache and starts no broker poller.

Set the export URL and secret on the bot, and set the same secret on the web service.
Use the Railway private domain for `STATE_EXPORT_URL`.
The bot sends its newest signed snapshot with at most 50 events outside the trading path.
The web boundary rejects oversized, expired, invalid, repeated, or stale snapshots.

| response | browser lifetime |
| --- | ---: |
| account, positions, open orders, run, events | 5 seconds |
| newest closed orders and fills | 15 seconds |
| historical order and fill pages | 5 minutes |
| equity and P&L history | 1 minute |

<!-- ddoc:names -->
| lemma | count | alternatives |
| --- | ---: | --- |
| analyze | 1 | analysis |
<!-- /ddoc:names -->
