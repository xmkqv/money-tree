# [solid-primitives: event listener][@solid-primitives/event-listener:docs]

## immediate subscription

```ts
import { makeEventListener } from "@solid-primitives/event-listener"

stop = makeEventListener(window, "keydown", event => select(event.key))
stop()
```

## mounted element

```tsx
import { onMount } from "solid-js"
import { makeEventListener } from "@solid-primitives/event-listener"

Panel = () => {
    let element!: HTMLDivElement
    onMount(() => {
        makeEventListener(element, "scroll", event => measure(event.currentTarget), {
            passive: true,
        })
    })
    return <div ref={element} />
}
```

## reactive target

```ts
import { createSignal } from "solid-js"
import { createEventListener } from "@solid-primitives/event-listener"

[target, setTarget] = createSignal<HTMLElement>()
createEventListener(target, "pointermove", event => render(event.clientX))
setTarget(element)
```

## refs

[@solid-primitives/event-listener:docs]: https://primitives.solidjs.community/package/event-listener/
    Event listener is automatically removed on root cleanup
    when listening to element refs, call it inside onMount

[@solid-primitives/event-listener:source]: https://github.com/solidjs-community/solid-primitives/tree/main/packages/event-listener

[@solid-primitives/event-listener:version]: https://registry.npmjs.org/@solid-primitives/event-listener/2.4.6
