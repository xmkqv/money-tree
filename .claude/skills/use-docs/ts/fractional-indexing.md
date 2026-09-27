# [fractional-indexing][fractional-indexing:docs]

## first key

```ts
import { generateKeyBetween } from "fractional-indexing"

first = generateKeyBetween(null, null)
```

## neighbour bounds

```ts
before = generateKeyBetween(null, items[0]?.key ?? null)
after = generateKeyBetween(items.at(-1)?.key ?? null, null)
between = generateKeyBetween(items[at - 1]?.key ?? null, items[at]?.key ?? null)
```

## batch keys

```ts
import { generateNKeysBetween } from "fractional-indexing"

keys = generateNKeysBetween(lower, upper, drafts.length)
```

## ordered read

```ts
sorted = [...items].sort((a, b) => (a.key < b.key ? -1 : a.key > b.key ? 1 : 0))
```

## refs

[fractional-indexing:docs]: https://github.com/rocicorp/fractional-indexing
    generateKeyBetween throws when lower ≥ upper or a key is malformed
    keys order by code unit; store them under a byte-wise collation
    keys are base62 text and never end in the smallest digit

[fractional-indexing:version]: https://registry.npmjs.org/fractional-indexing/4.0.0
