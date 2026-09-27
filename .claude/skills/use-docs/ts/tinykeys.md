# [tinykeys][tinykeys:docs]

## bindings

```ts
import { tinykeys } from "tinykeys"

unsubscribe = tinykeys(window, {
    "Shift+d": () => …,
    "$mod+k": event => { event.preventDefault(); … },
    "g i": () => …,               // sequence
    "([0-9])": event => useTab(event.key),
    "[Shift]+Enter": () => …,     // optional modifier
})
```

## options

```ts
tinykeys(target, bindings, {
    event: "keyup",               // default "keydown"
    timeout: 2000,                // ms between sequence presses, default 1000
    ignore: event => event.target?.closest("[role=dialog]") !== null,
})
```

## refs

[tinykeys:docs]: https://github.com/jamiebuilds/tinykeys#readme
    Mac: `$mod` = `Meta` (⌘), Windows/Linux: `$mod` = `Control`
