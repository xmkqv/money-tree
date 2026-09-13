# @solid-primitives/event-bus

## typed emitter

```ts
import { createEmitter } from "@solid-primitives/event-bus"

events = createEmitter<{ opened: string; closed: void }>()
stop = events.on("opened", value => render(value))
events.emit("opened", "panel")
events.emit("closed")
stop()
```

## independent lifetime

```ts
import { createRoot } from "solid-js"
import { createEmitter } from "@solid-primitives/event-bus"

events = createRoot(() => createEmitter<{ changed: number }>())

createRoot(dispose => {
    events.on("changed", value => render(value))
    events.emit("changed", 1)
    dispose()
})
```

## tips

- [`on`][docs] registers subscriber cleanup and returns an unsubscribe function.
- Emitter creation registers `clear`; shared emitters need [independent ownership][root].
- [Dispatch][source] is synchronous; listener exceptions propagate to the emitter's caller.
- [Version 1][version] supports Solid 1; inspect peers before selecting prerelease versions.

## refs

[docs]: https://primitives.solidjs.community/package/event-bus/
[source]: https://github.com/solidjs-community/solid-primitives/blob/main/packages/event-bus/src/emitter.ts
[root]: https://docs.solidjs.com/reference/reactive-utilities/create-root
[version]: https://registry.npmjs.org/@solid-primitives/event-bus/1.1.4
