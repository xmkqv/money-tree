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
            base.py
            noop.py
            {name}.py
            ...
        portfolio.py # multi-strategy composer
        config.py
        backtest.py
        report.py
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

# report

```sh
mt report --strategy {name} --symbols {symbols} --start {date} --end {date}
    → runs/{name}-{start}-{end}/{stats.csv,trades.csv,settings.json,backtest.log,plot.html,indicators.html,tearsheet.html,tearsheet_metrics.json}
```

# dashboard

| response                                     | browser lifetime |
|----------------------------------------------|-----------------:|
| account, positions, open orders, run, events |        5 seconds |
| newest closed orders and fills               |       15 seconds |
| historical order and fill pages              |        5 minutes |
| equity and P&L history                       |         1 minute |
