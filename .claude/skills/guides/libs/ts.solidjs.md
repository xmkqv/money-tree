# ts solidjs

[ts](../code/ts.md)
[catalog](../../catalogs/vite-solidjs.md)

- use `solid-js@^1.9`
- a primary component is a named default function export

## types

### reactive props

```tsx
type ShelfLabelProps = { title: string };
export default function ShelfLabel(props: ShelfLabelProps) {
  return <p>Shelf {props.title}</p>;
}
```

### native wrapper

```tsx
import { splitProps, type JSX } from "solid-js";
type ButtonTone = "quiet" | "strong";
type ButtonProps = JSX.ButtonHTMLAttributes<HTMLButtonElement> & {
  tone?: ButtonTone;
};
export default function Button(props: ButtonProps) {
  const [local, buttonProps] = splitProps(props, ["tone"]);
  return <button {...buttonProps} data-tone={local.tone ?? "quiet"} />;
}
```

## flow

### keyed branch

```tsx
import { Show } from "solid-js";
<Show when={props.book} keyed fallback={<EmptySlot />}>
  {(book) => <BookCard book={book} />}
</Show>
```

## fallibility

### async boundary

```tsx
import { createResource, ErrorBoundary, Show, Suspense } from "solid-js";
export default function ShelfPanel(props: ShelfPanelProps) {
  const [shelf] = createResource(() => props.shelfId, fetchShelf);

  return (
    <ErrorBoundary fallback={(error) => <p role="alert">{String(error)}</p>}>
      <Suspense fallback={<p>Loading…</p>}>
        <Show when={shelf()} keyed>
          {(value) => <SlotGrid shelf={value} />}
        </Show>
      </Suspense>
    </ErrorBoundary>
  );
}
```

## state

### functional signal update

```tsx
import { createSignal } from "solid-js";
export default function BorrowCounter() {
  const [count, setCount] = createSignal(0);
  const handleBorrow = () => setCount((value) => value + 1);
  return (
    <button type="button" onClick={handleBorrow}>
      Borrow ({count()})
    </button>
  );
}
```

### pure memo

```tsx
import { createMemo, For } from "solid-js";
export default function BookList(props: BookListProps) {
  const shelvedBooks = createMemo(() =>
    props.books.filter((book) => book.shelved)
  );
  return (
    <ul>
      <For each={shelvedBooks()}>{(book) => <li>{book.title}</li>}</For>
    </ul>
  );
}
```

## boundaries

### typed event

```tsx
import type { JSX } from "solid-js";
export default function SearchField(props: SearchFieldProps) {
  const handleInput: JSX.EventHandler<HTMLInputElement, InputEvent> = (event) => {
    props.onQueryChange(event.currentTarget.value);
  };
  return <input type="search" aria-label="Search" onInput={handleInput} />;
}
```
