# [rich][rich:docs]

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

## refs

[rich:docs]: https://rich.readthedocs.io/en/stable/

[rich:console]: https://rich.readthedocs.io/en/stable/console.html

[rich:protocol]: https://rich.readthedocs.io/en/stable/protocol.html
