---
refs:
    - [Lumibot](https://github.com/Lumiwealth/lumibot#quick-start)
    - [environment](./mise.{MISE_ENV}.toml)
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

# env

```yaml:bot
env:
  - STRATEGIES
  - ALPACA_API_KEY
  - ALPACA_API_SECRET
  - ALPACA_IS_PAPER
  - ALPACA_DATA_FEED
  - FRACTIONAL_ORDERS
  - RISK_PER_DAY_MAX
  - RISK_PER_TRADE_MAX
  - POSITION_FRACTION_MAX
  - STATE_EXPORT_URL
  - STATE_EXPORT_SECRET
```

```yaml:ui
env:
  - PORT
  - APP_BASE_URL
  - ALLOWED_RAILWAY_EMAILS
  - RAILWAY_OAUTH_CLIENT_ID
  - RAILWAY_OAUTH_CLIENT_SECRET
  - RAILWAY_OAUTH_REDIRECT_URI
  - SESSION_SECRET
  - SESSION_TTL_SECONDS
  - ALPACA_API_KEY
  - ALPACA_API_SECRET
  - ALPACA_IS_PAPER
  - FRACTIONAL_ORDERS
  - POSITION_FRACTION_MAX
  - RISK_PER_DAY_MAX
  - RISK_PER_TRADE_MAX
  - STATE_EXPORT_SECRET
```

# deploy

[bot → web](./.railway/railway.ts)

```yaml:deploy
env:
  - MODE
  - RAILWAY_TOKEN
```

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
