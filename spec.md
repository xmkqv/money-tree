---
name: spec
---

```sql:types
type node = (feed, venue, strategy) → session
```

## node

```text:rules
live(feed)
simulated(venue)
seeded(instrument) precedes connect(node)
```

## strategy

```text:rules
flat(strategy) → enter(side(fast_ema, slow_ema))
open(position) → attached(trailing_stop)
rejected(trailing_stop) → flatten(position)
```
