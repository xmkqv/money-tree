# py

## form

- py:form:code`*`


## types

### opaque identifier

```py
from typing import NewType


BookId = NewType("BookId", str)
```

### constrained value

```py
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ShelfKey:
    value: str

    def __post_init__(self) -> None:
        value = self.value.strip()
        if not value:
            raise ValueError("shelf key must not be blank")
        object.__setattr__(self, "value", value)
```

### closed mode

```py
from enum import StrEnum


class LoanMode(StrEnum):
    STANDARD = "standard"
    SHORT = "short"
```

### capability

```py
from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...
```

### exhaustive state

```py
from typing import assert_never


def loan_days(mode: LoanMode) -> int:
    match mode:
        case LoanMode.STANDARD:
            return 21
        case LoanMode.SHORT:
            return 7
    assert_never(mode)
```

## collections

### materialized transform

```py
titles = [book.title.strip() for book in books if book.is_shelved]
```

### keyed transform

```py
books_by_id = {book.id: book for book in books}
```

### lazy aggregation

```py
page_count = sum(book.page_count for book in books if book.is_shelved)
```

### strict alignment

```py
loans = [Loan(book, due_on) for book, due_on in zip(books, due_dates, strict=True)]
```

### named complex traversal

```py
from collections.abc import Iterable, Iterator
from datetime import date


def iter_overdue(loans: Iterable[Loan], today: date) -> Iterator[Loan]:
    for loan in loans:
        if loan.returned_on is not None:
            continue
        if loan.due_on >= today:
            continue
        yield loan
```

## generics

### type-preserving selection

```py
from collections.abc import Sequence


def first[Value](values: Sequence[Value], /) -> Value:
    if not values:
        raise ValueError("values must not be empty")
    return values[0]
```

### keyed collection

```py
from collections.abc import Callable, Hashable, Iterable


def index_by[Key: Hashable, Value](
    values: Iterable[Value],
    *,
    key: Callable[[Value], Key],
) -> dict[Key, Value]:
    return {key(value): value for value in values}
```

### validated page

```py
from pydantic import BaseModel, ConfigDict, NonNegativeInt


class Page[Item](BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    items: list[Item]
    total: NonNegativeInt
```

### signature-preserving decorator

```py
import logging
from collections.abc import Callable
from functools import wraps


logger = logging.getLogger(__name__)


def traced[**Params, Return](
    function: Callable[Params, Return],
) -> Callable[Params, Return]:
    @wraps(function)
    def wrapped(*args: Params.args, **kwargs: Params.kwargs) -> Return:
        logger.debug("call %s", function.__qualname__)
        return function(*args, **kwargs)

    return wrapped
```

## boundaries

### strict boundary model

```py
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints


type Title = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]


class BookPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: UUID
    title: Title


def parse_book(payload: bytes) -> BookPayload:
    return BookPayload.model_validate_json(payload)
```

### cross-field invariant

```py
from datetime import date
from typing import Self

from pydantic import BaseModel, model_validator


class LoanDatesPayload(BaseModel):
    borrowed_on: date
    due_on: date

    @model_validator(mode="after")
    def check_due_on(self) -> Self:
        if self.due_on <= self.borrowed_on:
            raise ValueError("due date must follow borrow date")
        return self
```

### discriminated union

```py
from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter


class StandardLoanPayload(BaseModel):
    mode: Literal["standard"]
    days: Literal[21]


class ShortLoanPayload(BaseModel):
    mode: Literal["short"]
    days: Literal[7]


type LoanPayload = Annotated[
    StandardLoanPayload | ShortLoanPayload,
    Field(discriminator="mode"),
]

loan_adapter = TypeAdapter(LoanPayload)
loan = loan_adapter.validate_json(payload)
```

### adapted collection

```py
from pydantic import TypeAdapter


book_list_adapter = TypeAdapter(list[BookPayload])
books = book_list_adapter.validate_json(payload)
```

## fallibility

### contextual error

```py
from pathlib import Path


class LoadCatalogError(Exception):
    pass


def load_catalog(path: Path) -> Catalog:
    try:
        text = path.read_text()
    except OSError as error:
        raise LoadCatalogError(f"catalog {path} could not be read") from error
    return parse_catalog(text)
```

### expected absence

```py
def find_book(books: Iterable[Book], id: BookId) -> Book | None:
    return next((book for book in books if book.id == id), None)
```

### symmetric narrowing

```py
from typing import TypeIs


def is_book(item: Item) -> TypeIs[Book]:
    return isinstance(item, Book)
```

## lifecycle

### transactional context

```py
from collections.abc import Iterator
from contextlib import contextmanager
from sqlite3 import Connection, Cursor


@contextmanager
def transaction(connection: Connection) -> Iterator[Cursor]:
    cursor = connection.cursor()
    try:
        yield cursor
    except BaseException:
        connection.rollback()
        raise
    else:
        connection.commit()
    finally:
        cursor.close()
```

### structured concurrency

```py
from asyncio import TaskGroup
from collections.abc import Sequence


async def load_shelves(ids: Sequence[ShelfId]) -> dict[ShelfId, Shelf]:
    async with TaskGroup() as tasks:
        pending = {
            shelf_id: tasks.create_task(load_shelf(shelf_id), name=str(shelf_id))
            for shelf_id in ids
        }
    return {shelf_id: task.result() for shelf_id, task in pending.items()}
```

## verification

- ruff lints and formats; pyright checks types

### strict type check

```toml
[tool.pyright]
pythonVersion = "3.14"
typeCheckingMode = "strict"
```
