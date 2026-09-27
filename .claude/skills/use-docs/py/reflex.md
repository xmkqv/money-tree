# [reflex][reflex:docs]

[0.9.10.post2][reflex:release] · Python `>=3.10,<4.0` · released 2026-09-08

## state

[`class State(rx.State)`][reflex:state] → reactive state

```py
import reflex as rx

class State(rx.State):
    items: list[str] = []
    selected: str = ""
    value: float = 0.0
    is_loading: bool = False
    is_running: bool = False
```

## events

[`@rx.event def handler(self, *args)`][reflex:events] → EventHandler

```py
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

[`@rx.var(cache=True)`][reflex:vars] → dependency-cached value

```py
class State(rx.State):
    ...

    @rx.var
    def value_label(self) -> str:
        return f"{self.value:,.2f}"

rx.text(State.value_label)
```

## conditional rendering

[`rx.cond(condition, if_true, if_false)`][reflex:cond] → Component | Var

```py
rx.cond(State.value >= 0, rx.text("nonnegative"), rx.text("negative"))
rx.badge(
    State.selected,
    color_scheme=rx.cond(State.value >= 0, "green", "red"),
)
```

## iteration

[`rx.foreach(iterable, render_fn)`][reflex:foreach] → Component

```py
rx.foreach(
    State.items,
    lambda item, index: rx.hstack(
        rx.text(index),
        rx.button(item, on_click=State.select(item)),
    ),
)
```

## matching

[`rx.match(condition, *cases)`][reflex:match] → Component | Var

```py
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

[`@rx.event(background=True) async def task(self)`][reflex:background-events] → concurrent EventHandler

```py
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

[`class Widget(rx.NoSSRComponent)`][reflex:wrapping-react] + [`library` / `tag` / props][reflex:props] → React component

```py
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

[`app.add_page(component, route=None, title=None, on_load=None, meta=[])`][reflex:app] → None

```py
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

## refs

[reflex:docs]: https://reflex.dev/docs/getting-started/introduction

[reflex:release]: https://pypi.org/project/reflex/0.9.10.post2/

[reflex:state]: https://reflex.dev/docs/state/overview

[reflex:events]: https://reflex.dev/docs/events/yield-events
    we can `yield` when we want to send an update

[reflex:vars]: https://reflex.dev/docs/vars/computed-vars

[reflex:cond]: https://reflex.dev/docs/library/dynamic-rendering/cond

[reflex:foreach]: https://reflex.dev/docs/library/dynamic-rendering/foreach
    dicts are passed to `render_fn` as key-value tuples with string keys

[reflex:match]: https://reflex.dev/docs/library/dynamic-rendering/match

[reflex:background-events]: https://reflex.dev/docs/events/background-events

[reflex:wrapping-react]: https://reflex.dev/docs/wrapping-react/overview

[reflex:props]: https://reflex.dev/docs/wrapping-react/props

[reflex:app]: https://reflex.dev/docs/api-reference/app

[reflex:pages]: https://reflex.dev/docs/pages/overview
    By default, the function name will be used as the route

[reflex:config]: https://reflex.dev/docs/api-reference/config

[reflex:queries]: https://reflex.dev/docs/database/queries
    `rx.asession` needs its own `async_db_url` in `rxconfig.py`
