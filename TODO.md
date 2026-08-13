---
name: TODO
guides: names, code:python
---

STRATEGY_PAGE_URL=https://app.notion.com/p/Strategy-3ba2876aac86805894f4db4de547cf12

[ ] adopt the lumibot + alpaca stack; drop dead installs and scripts

```bash
src/
    broker.py
    strategies/
        {name}.py
        ...
```

[ ] (ntn cli) add the [obr](https://app.notion.com/p/Strategy-3ba2876aac86805894f4db4de547cf12?source=copy_link#3bb2876aac8680e1b7ffdfa3227de388) strategy

[ ] run it with live money; limit daily total risk to $1 i.e. scale trade sizes down and enforce a global stop loss
