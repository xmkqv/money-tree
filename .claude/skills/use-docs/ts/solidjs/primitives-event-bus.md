# [solid-primitives: event bus][@solid-primitives/event-bus:docs]

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

## refs

[@solid-primitives/event-bus:docs]: https://primitives.solidjs.community/package/event-bus/

[@solid-primitives/event-bus:source]: https://github.com/solidjs-community/solid-primitives/blob/main/packages/event-bus/src/emitter.ts

[solid-js:create-root]: https://docs.solidjs.com/reference/reactive-utilities/create-root

[@solid-primitives/event-bus:version]: https://registry.npmjs.org/@solid-primitives/event-bus/1.1.4
