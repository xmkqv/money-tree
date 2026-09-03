---
refs:
    - [Lumibot](https://github.com/Lumiwealth/lumibot#quick-start)
---

# code

```sh
src/
    bot/
        strategies/
            base.py
            daily_base.py
            orb_base.py
            shared.py
            tfb_50.py
        backtest.py
        broker.py
        config.py
        export.py
        order_tag.py
        portfolio.py
        report.py
        trade.py
        types.py
    cli/
        __main__.py
    ui/
        assets/
            dashboard.css
            dashboard.html
            dashboard.js
            favicon.svg
            theme.js
        alpaca.py
        app.py
        auth.py
        config.py
        dashboard.py
        ledger.py
        strategies.py
```

# deploy

[bot → web](./.railway/railway.ts)

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

# claims

- the bot runs multiple strategies
- the ui renders a modern dashboard that includes an overview, strategy details, analysis, and logs
- the selected mise mode supplies every deployed service variable
