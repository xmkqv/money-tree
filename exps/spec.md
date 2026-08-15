---
name: research
terms: ../names.yaml
---

# boundary

- this research estimates break-even directional accuracy for aapl momentum[15m]
- this research does not evaluate opening-range or momentum-long
- research output is not product-strategy evidence
- market observations come from the alpaca sip feed

# round trip

- one share enters and flattens during each active horizon
- each fill crosses an assumed three-cent spread
- market impact is zero by assumption

# cost

- explicit fees use the stated commission and regulatory fee rates
- regulatory fees include the section 31 fee, finra trading activity fee, and cat fee
- fee amounts round upward to the nearest cent by trading session

# break-even accuracy

- correct and incorrect forecasts have equal mean absolute price moves
- the estimand is the directional accuracy that offsets mean transaction cost
- the stationary bootstrap preserves local dependence between sessions
- the upper confidence bound uses a one-sided 95 percent bca interval
