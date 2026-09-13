# solid-js

## reactive props

```tsx
Label = props => <span>{props.value}</span>
```

## native wrapper

```tsx
import { splitProps } from "solid-js"
Input = props => {
    [local, rest] = splitProps(props, ["label"])
    return <label>{local.label}<input {...rest} /></label>
}
```

## async boundary

```tsx
import { createResource, ErrorBoundary, Suspense, Show } from "solid-js"
Panel = props => {
    [data] = createResource(() => props.id, fetchValue)
    return <ErrorBoundary fallback={error => <p>{String(error)}</p>}>
        <Suspense fallback={<p>Loading…</p>}>
            <Show when={data()} keyed>{value => <Detail value={value} />}</Show>
        </Suspense>
    </ErrorBoundary>
}
```

## functional update

```tsx
import { createSignal } from "solid-js"
Counter = () => {
    [count, setCount] = createSignal(0)
    return <button onClick={() => setCount(value => value + 1)}>{count()}</button>
}
```

## memoized projection

```tsx
import { createMemo, For } from "solid-js"
List = props => {
    selected = createMemo(() => props.items.filter(item => item.selected))
    return <For each={selected()}>{item => <span>{item.label}</span>}</For>
}
```

## typed event

```tsx
import type { JSX } from "solid-js"
handleInput: JSX.EventHandler<HTMLInputElement, InputEvent> = event =>
    setValue(event.currentTarget.value)
```

## tips

- props remain reactive when read through their properties.
- `splitProps` preserves reactive access while separating wrapper props.
- keyed `Show` passes the resolved value to its child function.
- [resources][resource] connect asynchronous values to suspense boundaries.

## refs

[resource]: https://docs.solidjs.com/reference/basic-reactivity/create-resource
