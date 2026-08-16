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
mt trade --strategy "$STRATEGY"
mt backtest --strategy "$STRATEGY" --start "$BACKTEST_START" --end "$BACKTEST_END"
uvicorn ui.app:create_app --factory --workers 1 --host "" --port "$PORT"
```

`railway.toml` runs the bot. `railway.web.toml` runs the web service on one replica.
The bot reaches the web service on the Railway private domain.
The web service holds a separate paper Alpaca credential for named GET requests.

The bot sends its newest signed snapshot with at most 50 events outside the trading path.
The web boundary rejects oversized, expired, invalid, repeated, or stale snapshots.

The dashboard reads each URL separately. FastAPI keeps no broker cache and starts no broker poller.

| response | browser lifetime |
| --- | ---: |
| account, positions, open orders, run, events | 5 seconds |
| newest closed orders and fills | 15 seconds |
| historical order and fill pages | 5 minutes |
| equity and P&L history | 1 minute |
