# money-tree

```text:rules
count(interface(layer)) = 1
count(input(interface)) = 1
count(output(interface)) = 1
selects(config, instance(layer))
external(composition)
external(execution)
```

```sql:types
type name = (text)
type config = (name)
type interface = (config, input) → output
```

```md:api
data(data_config, source): grain
model(model_config, grain): prediction
decider(decider_config, prediction): decision
trader(trader_config, decision): outcome
```

## data

```text:rules
owns(data, access)
locked(pipe)
pipe(data) = grain(dlt(source))
```

```sql:types
type source = (name, spec)
type grain = (key, time, fields)
type data_config = (name, source, grain)
type data = (data_config, source) → grain
```

### live

```text:rules
tentative(live)
unbounded(source(live))
incremental(grain(live))
```

```sql:types
type live = (data_config, source) → stream(grain)
```

### past

```text:rules
tentative(past)
bounded(source(past))
complete(grain(past))
```

```sql:types
type window = (start, end)
type past = (data_config, window) → batch(grain)
```

## models

```text:rules
owns(models, transform)
owns(models, predict)
```

```sql:types
type prediction = (name, value)
type model_config = (name, operation)
type model = (model_config, grain) → prediction
```

## deciders

```text:rules
owns(deciders, decision_formation)
```

```sql:types
type decision = (name, value)
type decider_config = (name, operation)
type decider = (decider_config, prediction) → decision
```

## traders

```text:rules
owns(traders, decision_execution)
```

```sql:types
type outcome = (name, value)
type trader_config = (name, operation)
type trader = (trader_config, decision) → outcome
```
