# reflex

[0.9.10.post2][release] · Python `>=3.10,<4.0` · released 2026-09-08

## state

[`class State(rx.State)`][state] → reactive state

```python
import reflex as rx

class State(rx.State):
    items: list[str] = []
    selected: str = ""
    value: float = 0.0
    is_loading: bool = False
    is_running: bool = False
```

## events

[`@rx.event def handler(self, *args)`][events] → EventHandler

```python
class State(rx.State):
    ...

    @rx.event
    def select(self, value: str):
        self.selected = value

    @rx.event
    async def reload(self):
        self.is_loading = True
        yield
        try:
            self.items = await fetch_items()
        finally:
            self.is_loading = False

rx.button("Reload", on_click=State.reload, loading=State.is_loading)
```

## computed vars

[`@rx.var(cache=True)`][vars] → dependency-cached value

```python
class State(rx.State):
    ...

    @rx.var
    def value_label(self) -> str:
        return f"{self.value:,.2f}"

rx.text(State.value_label)
```

## conditional rendering

[`rx.cond(condition, if_true, if_false)`][cond] → Component | Var

```python
rx.cond(State.value >= 0, rx.text("nonnegative"), rx.text("negative"))
rx.badge(
    State.selected,
    color_scheme=rx.cond(State.value >= 0, "green", "red"),
)
```

## iteration

[`rx.foreach(iterable, render_fn)`][foreach] → Component

```python
rx.foreach(
    State.items,
    lambda item, index: rx.hstack(
        rx.text(index),
        rx.button(item, on_click=State.select(item)),
    ),
)
```

## matching

[`rx.match(condition, *cases)`][match] → Component | Var

```python
rx.match(
    State.selected,
    ("a", rx.text("First")),
    ("b", rx.text("Second")),
    ("c", "d", rx.text("Other")),
    rx.text("None selected"),
)
rx.badge(State.selected, color_scheme=rx.match(State.selected, ("a", "green"), "gray"))
```

## background events

[`@rx.event(background=True) async def task(self)`][background] → concurrent EventHandler

```python
class State(rx.State):
    ...

    @rx.event(background=True)
    async def reload_background(self):
        async with self:
            if self.is_running:
                return
            self.is_running = True
        try:
            items = await fetch_items()
            async with self:
                self.items = items
        finally:
            async with self:
                self.is_running = False

    @rx.event
    def start(self):
        return State.reload_background
```

## React wrappers

[`class Widget(rx.NoSSRComponent)`][wrapping] + [`library` / `tag` / props][props] → React component

```python
class ColorPicker(rx.NoSSRComponent):
    library = "react-colorful@5.7.0"
    tag = "HexColorPicker"
    color: rx.Var[str]
    on_change: rx.EventHandler[lambda color: [color]]

color_picker = ColorPicker.create

class ColorState(rx.State):
    color: str = "#ffffff"

    @rx.event
    def set_color(self, value: str):
        self.color = value

color_picker(color=ColorState.color, on_change=ColorState.set_color)
```

## pages

[`app.add_page(component, route=None, title=None, on_load=None, meta=[])`][app] → None

```python
def index():
    return rx.vstack(
        rx.button("Reload", on_click=State.reload),
        rx.foreach(State.items, lambda item: rx.text(item)),
    )

app = rx.App(style={"font_family": "sans-serif"})
app.add_page(index, route="/", title="Items", on_load=State.reload)

# Alternative registration:
@rx.page(route="/items", title="Items", on_load=State.reload)
def items_page():
    return index()
```

## tips

- Read `State.selected` in components; write `self.selected` inside event handlers.
- `yield` sends intermediate state; `fetch_items()` stands for an asynchronous data source.
- `cache=False` recomputes on every state update; computed vars are read-only.
- Comprehensions handle constants; `rx.foreach` renders state lists and dict key/value pairs.
- Background writes need `async with self`; unlocked writes raise `ImmutableStateError`.
- Trigger background handlers with `yield` or `return`; direct calls are unsupported.
- `@rx.event(background=True)` replaces `@rx.background`.
- Use `rx.Component` normally; `NoSSRComponent` handles browser-only `window`/`document` access.
- [`@rx.page`][pages] is the decorator form; omitted routes derive from function names.

- [Database][queries] needs `reflex[db]` and `db_url`; async sessions need `async_db_url`.
- Shared state across workers uses `redis_url` (`REFLEX_REDIS_URL`); see [configuration][config].
- Frontend compilation requires Bun or Node; serving a compiled frontend needs no rebuild.

## refs

[release]: https://pypi.org/project/reflex/0.9.10.post2/
[state]: https://reflex.dev/docs/state/overview
[events]: https://reflex.dev/docs/events/yield-events
[vars]: https://reflex.dev/docs/vars/computed-vars
[cond]: https://reflex.dev/docs/library/dynamic-rendering/cond
[foreach]: https://reflex.dev/docs/library/dynamic-rendering/foreach
[match]: https://reflex.dev/docs/library/dynamic-rendering/match
[background]: https://reflex.dev/docs/events/background-events
[wrapping]: https://reflex.dev/docs/wrapping-react/overview
[props]: https://reflex.dev/docs/wrapping-react/props
[app]: https://reflex.dev/docs/api-reference/app
[pages]: https://reflex.dev/docs/pages/overview
[config]: https://reflex.dev/docs/api-reference/config
[queries]: https://reflex.dev/docs/database/queries
[upgrade]: https://reflex.dev/blog/upgrading-reflex-0-8-to-0-9
