# @solid-primitives/event-listener

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

## tips

- [`makeEventListener`][docs] subscribes immediately and removes the listener on owner cleanup.
- [`createEventListener`][source] registers through an effect and tracks reactive targets and names.
- Use `onMount` when subscribing through an element ref.
- [Version 2][version] supports Solid 1; inspect peers before selecting prerelease versions.

## refs

[docs]: https://primitives.solidjs.community/package/event-listener/
[source]: https://github.com/solidjs-community/solid-primitives/tree/main/packages/event-listener
[version]: https://registry.npmjs.org/@solid-primitives/event-listener/2.4.6
