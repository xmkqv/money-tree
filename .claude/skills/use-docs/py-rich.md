# rich

## scoped capture

```py
from rich.console import Console
console = Console(stderr=True)
with console.capture() as capture:
    console.print("[bold]complete[/bold]")
message = capture.get()
```

## recorded export

```py
recorded = Console(record=True)
recorded.print(renderable)
html = recorded.export_html()
svg = recorded.export_svg()
```

## composite renderable

```py
from rich.console import Group
from rich.panel import Panel
from rich.text import Text
console.print(Group(Panel(Text(title)), Text(detail)))
```

## custom render protocol

```py
from dataclasses import dataclass
from rich.text import Text
@dataclass(frozen=True)
class Record:
    label: str
    detail: str
    def __rich_console__(self, console, options):
        yield Text(self.label, style="bold")
        yield Text(self.detail)
```

## tips

- capture returns one local text result; recording retains output for later export.
- html and svg exports represent terminal output.
- `__rich__` returns one renderable; `__rich_console__` yields several.
- `__rich_measure__` supplies custom width calculation.
- [the console reference][console] covers capture, recording, and output destinations.

## refs

[console]: https://rich.readthedocs.io/en/stable/console.html
