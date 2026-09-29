# [typer][typer:docs]

0.27.2 · vendors Click (no third-party Click dependency) · Python 3.10+ syntax · [changes][typer:changelog]

## app with subcommands

[`Typer(no_args_is_help=False, add_completion=True, rich_markup_mode=…, pretty_exceptions_enable=True, suggest_commands=True, context_settings=None, …)`][typer:docs]; `add_typer(app, name=…)` mounts a group.

```py
import typer

app = typer.Typer(no_args_is_help=True, add_completion=False, pretty_exceptions_enable=False)
users = typer.Typer(no_args_is_help=True, help="Manage users.")
app.add_typer(users, name="users")


@users.command("list")
def list_users() -> None:
    typer.echo("…")


if __name__ == "__main__":
    app()
```

## options from annotations

[`typer.Option(default, *param_decls, help, envvar, callback, min, max, show_default, …)`][typer:params] inside `Annotated`; a plain default makes a flag, no default makes it required.

```py
from typing import Annotated


@app.command()
def run(
    name: Annotated[str, typer.Option(help="Target name.", envvar="APP_NAME")],
    retries: Annotated[int, typer.Option(min=0, max=5, clamp=True)] = 1,
    dry_run: Annotated[bool, typer.Option("--dry-run/--no-dry-run", "-n")] = False,
    verbose: Annotated[int, typer.Option("--verbose", "-v", count=True)] = 0,
) -> None: ...
```

## choices from enums and literals

An `Enum` or `Literal` annotation becomes a choice list; enum members are matched by value.

```py
from enum import StrEnum
from typing import Literal


class Mode(StrEnum):
    PAPER = "paper"
    LIVE = "live"


@app.command()
def start(
    mode: Annotated[Mode, typer.Option(case_sensitive=False)] = Mode.PAPER,
    level: Annotated[Literal["low", "high"], typer.Option()] = "low",
) -> None:
    typer.echo(mode.value)
```

## repeated values

`list[T]` makes an option repeatable as `--item a --item b`; the element type must be simple (no `Literal`, no union).

```py
@app.command()
def add(
    items: Annotated[list[Mode], typer.Option("--item")],
    tags: Annotated[list[str] | None, typer.Option("--tag")] = None,
    pair: Annotated[tuple[str, int], typer.Option()] = ("a", 1),
) -> None: ...
```

## datetime and path types

`datetime` parses `formats`, defaulting to naive ISO formats; `Path` accepts filesystem checks.

```py
from datetime import datetime
from pathlib import Path


@app.command()
def report(
    start: Annotated[datetime, typer.Option(formats=["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S%z"])],
    out: Annotated[Path, typer.Option(dir_okay=False, writable=True, resolve_path=True)],
) -> None: ...
```

## custom parsing

`parser=callable(str)` converts one raw value; raise `typer.BadParameter` for a usage error. `click_type=` takes a `ParamType`.

```py
def parse_symbols(value: str) -> list[str]:
    symbols = [item.strip().upper() for item in value.split(",") if item.strip()]
    if len(set(symbols)) != len(symbols):
        raise typer.BadParameter("symbols must be distinct")
    return symbols


@app.command()
def scan(symbols: Annotated[list[str], typer.Option(parser=parse_symbols)]) -> None: ...
```

## validation callbacks

`callback(value)` or `callback(ctx, param, value)` returns the value to use; `is_eager=True` runs first.

```py
def check_range(ctx: typer.Context, param: typer.CallbackParam, value: int) -> int:
    if value % 2:
        raise typer.BadParameter(f"{param.name} must be even")
    return value


def version(value: bool) -> None:
    if value:
        typer.echo("1.0")
        raise typer.Exit()


@app.callback()
def main(
    version_: Annotated[bool, typer.Option("--version", callback=version, is_eager=True)] = False,
) -> None: ...
```

## group callback and shared context

`@app.callback()` runs before every subcommand; `ctx.obj` carries state.

```py
@app.callback()
def main(ctx: typer.Context, profile: Annotated[str, typer.Option()] = "default") -> None:
    ctx.obj = {"profile": profile}


@app.command()
def show(ctx: typer.Context) -> None:
    typer.echo(ctx.obj["profile"])
```

## lazy imports and exit codes

Import heavy modules inside the command so `--help` stays fast; `typer.Exit(code)` ends quietly, `typer.Abort()` prints "Aborted!".

```py
@app.command()
def trade(strategies: Annotated[list[Mode], typer.Option()]) -> None:
    from heavy.engine import run

    if not run(strategies):
        typer.echo("nothing to do", err=True)
        raise typer.Exit(code=2)
```

## testing

`typer.testing.CliRunner().invoke(app, args, input=None, env=None)` → `Result` with `exit_code`, `stdout`, `output`, `exception`.

```py
from typer.testing import CliRunner

runner = CliRunner()
result = runner.invoke(app, ["users", "list"], env={"APP_NAME": "x"})
assert result.exit_code == 0
assert "…" in result.stdout
```

## refs

[typer:docs]: https://typer.tiangolo.com/

[typer:params]: https://typer.tiangolo.com/reference/parameters
    When specifying *DateTime* formats, you should only pass a list or a tuple.

[typer:enum]: https://typer.tiangolo.com/tutorial/parameter-types/enum

[typer:callback]: https://typer.tiangolo.com/tutorial/options/callback-and-context

[typer:changelog]: https://typer.tiangolo.com/release-notes/
    Typer no longer depends on Click as a third party dependency
