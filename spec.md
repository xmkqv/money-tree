---
name: spec
refs:
    - [names](./names.yaml)
    - [env](./.env.example)
---

intruments: ...

```bash
src/money-tree/
    strategies/
        ...
    ...
exps/
    backtests/
        {strategy}.py
        ...
    ...
```

```sh
mt backtest --instrument {instrument} --strategy {strategy}
mt trade --instrument {instrument} --strategy {strategy} # paper
mt trade --instrument {instrument} --strategy {strategy} --LIVE # live
```
