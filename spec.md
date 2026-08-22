---
refs:
    - [Lumibot](https://github.com/Lumiwealth/lumibot#quick-start)
    - [env](./.env.example)
---

# code

```sh
src/
    analysis/
        break-even-accuracy.py
    cli/
        __main__.py
    bot/
        strategies/
            shared.py # strategy base class and loader
            noop.py # deployment-safe strategy that submits no orders
            portfolio.py # selected live strategy engines and portfolio risk
        config.py
        backtest.py
        broker.py
        export.py
        trade.py
    ui/
        assets/
            dashboard.v3.html
            dashboard.v3.css
            dashboard.v3.js
        alpaca.py
        dashboard.py
        config.py
        app.py
        auth.py
```

# deploy

[bot](./railway.toml) → [web](./railway.web.toml)

```sh
mt trade --strategies "$STRATEGIES"
mt backtest --strategy "${STRATEGIES%%,*}" --start 2023-01-01 --end 2024-01-01
uvicorn ui.app:create_app --factory --workers 1 --host "" --port "$PORT"
```

# dashboard

| response                                     | browser lifetime |
|----------------------------------------------|-----------------:|
| account, positions, open orders, run, events |        5 seconds |
| newest closed orders and fills               |       15 seconds |
| historical order and fill pages              |        5 minutes |
| equity and P&L history                       |         1 minute |
