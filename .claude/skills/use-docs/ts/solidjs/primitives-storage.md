# [solid-primitives: storage][@solid-primitives/storage:docs]

## persisted store

```ts
import { createStore } from "solid-js/store"
import { makePersisted } from "@solid-primitives/storage"

[items, setItems] = makePersisted(createStore<Item[]>([]), { name: "items" })
setItems(item => item.id === id, "label", label)
```

## persisted signal

```ts
[theme, setTheme] = makePersisted(createSignal("light"), { name: "theme", storage: sessionStorage })
```

## async storage

```ts
import localforage from "localforage"

[state, setState, init] = makePersisted(createStore({}), { name: "state", storage: localforage })
createResource(() => init)[0]()
```

## custom codec

```ts
[at, setAt] = makePersisted(createSignal(new Date()), {
    name: "at",
    serialize: value => value.toISOString(),
    deserialize: text => new Date(text),
})
```

## refs

[@solid-primitives/storage:docs]: https://primitives.solidjs.community/package/storage/
    localStorage is the default; a synchronous storage loads before the first read
    a store loads through reconcile, so identity of unchanged items survives
    an async load is dropped when the state changed before it resolved
    the setter proxies every store setter form and persists after each call

[@solid-primitives/storage:source]: https://github.com/solidjs-community/solid-primitives/blob/main/packages/storage/src/persisted.ts

[@solid-primitives/storage:version]: https://registry.npmjs.org/@solid-primitives/storage/4.4.0
