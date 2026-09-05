# py rich

[py](../code/py.md)
[rich documentation](https://rich.readthedocs.io)

- use `rich>=15,<16`
- use Rich for terminal presentation, not for semantic HTML or JSON structures
- create one application console and inject it where output policy differs
- send human diagnostics to stderr when stdout carries machine-readable data
- use capture for one local string and recording only when later export is required

## console

```py
from rich.console import Console


console = Console(stderr=True)
```

### local capture

```py
with console.capture() as capture:
    console.print("[bold]catalog ready[/bold]")

message = capture.get()
```

### recorded export

```py
from rich.console import Console


recorded = Console(record=True)
recorded.print(report)
transcript = recorded.export_text()
```

- `export_html()` and `export_svg()` export terminal transcripts
- do not use a Rich export when the target requires semantic headings, lists, or blocks

## renderables

- implement `__rich__` when one existing renderable represents the value
- implement `__rich_console__` when rendering yields a sequence
- implement `__rich_measure__` only for custom width calculation
- use `Group` when an API accepts one renderable but the output has several parts

```py
from dataclasses import dataclass

from rich.console import Console, ConsoleOptions, RenderResult
from rich.text import Text


@dataclass(frozen=True, slots=True)
class Book:
    title: str
    author: str

    def __rich_console__(
        self,
        console: Console,
        options: ConsoleOptions,
    ) -> RenderResult:
        yield Text(self.title, style="bold")
        yield self.author
```

- use `Markdown` only when Markdown must render into a terminal cell grid
- use `console.rule()` for a terminal divider
