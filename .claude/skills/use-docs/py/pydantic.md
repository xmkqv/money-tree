# [pydantic][pydantic:docs]

2.13.5 · pydantic-core 2.46.5 · Python 3.12+ syntax

```py
from datetime import date, datetime
from typing import Annotated, Literal, Self

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    Json,
    PlainSerializer,
    RootModel,
    TypeAdapter,
    ValidationError,
    computed_field,
    field_serializer,
    model_validator,
)
from pydantic.fields import FieldInfo
```

[`Annotated[T, Field(...)]`][pydantic:fields] → reusable constrained type; constraints live in the alias.

```py
type Count = Annotated[int, Field(gt=0)]
type Fraction = Annotated[float, Field(gt=0, le=1)]
type Identifier = Annotated[str, Field(min_length=1, pattern=r"^[a-z_]+$")]


class Item(BaseModel):
    name: Identifier
    ratio: Fraction
    quantity: Count = Field(validation_alias="qty")
    tags: tuple[Identifier, ...] = Field(default=(), max_length=8)
```

[`ConfigDict(validate_by_name, validate_by_alias, extra, frozen)`][pydantic:config] → payload model with wire aliases

```py
class Payload(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True, validate_by_name=True)


class Bar(Payload):
    opened_at: AwareDatetime = Field(alias="t")  # naive input → timezone_aware error
    close: float = Field(alias="c")  # "1.5" → 1.5 in lax mode
    volume: float = Field(alias="v", default=0.0)


class Page(Payload):
    bars: dict[str, list[Bar]] | None = None
    next_token: str | None = Field(alias="next_page_token", default=None)


bar = Bar(opened_at=datetime.now().astimezone(), close=1)  # by name
page = Page.model_validate_json(b'{"bars":{"X":[{"t":"2026-01-01T00:00:00Z","c":"1.5"}]}}')
```

[`TypeAdapter(type)`][pydantic:type-adapter] → `TypeAdapter[T]`; any type validates and dumps without a model.

```py
# Construct once at module level; reuse the compiled schema.
bars_adapter = TypeAdapter(list[Bar])
index_adapter = TypeAdapter(dict[str, Item])

bars = bars_adapter.validate_json(b'[{"t":"2026-01-01T00:00:00Z","c":1}]')  # bytes → typed, no dict hop
bars = bars_adapter.validate_python([{"t": "2026-01-01T00:00:00Z", "c": 1}])
body = bars_adapter.dump_json(bars)  # bytes
```

[`Field(discriminator=)`][pydantic:unions] → tagged union; the tag selects one member.

```py
class Cat(BaseModel):
    kind: Literal["cat"]
    lives: int


class Dog(BaseModel):
    kind: Literal["dog"]
    barks: bool


type Pet = Annotated[Cat | Dog, Field(discriminator="kind")]

pets = TypeAdapter(list[Pet]).validate_json(b'[{"kind":"dog","barks":"yes"}]')
# Callable discriminators: Annotated[Cat | Dog, Discriminator(fn)] with Tag("cat") per member.
```

[`BeforeValidator` / `AfterValidator` / `model_validator`][pydantic:validators] → input normalisation, then checks

```py
def split_csv(value: object) -> object:
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return value  # raw input, before coercion


def check_distinct[T](values: tuple[T, ...]) -> tuple[T, ...]:
    if len(set(values)) != len(values):
        raise ValueError("values must be distinct")  # becomes a ValidationError entry
    return values


type Selection = Annotated[
    tuple[Literal["a", "b", "c"], ...],
    BeforeValidator(split_csv),
    AfterValidator(check_distinct),
    Field(min_length=1),
]


class Window(BaseModel):
    start: datetime
    end: datetime

    @model_validator(mode="after")
    def check_order(self) -> Self:
        if self.end <= self.start:
            raise ValueError("end must follow start")
        return self


selection = TypeAdapter(Selection).validate_python("a, b")  # ("a", "b")
```

[`strict`, `ValidationError`][pydantic:strict] → lax coerces; strict rejects; failures carry structured details

```py
class Reading(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    value: float
    at: AwareDatetime


try:
    Reading.model_validate({"value": "1", "at": "2026-01-01T00:00:00Z"})  # python input: str rejected
except ValidationError as error:
    rows = error.errors(include_url=False, include_input=False)
    # [{"type": "float_type", "loc": ("value",), "msg": "Input should be a valid number"}, …]
    count = error.error_count()

reading = Reading.model_validate_json(b'{"value":1,"at":"2026-01-01T00:00:00Z"}')  # JSON input: int → float, str → datetime
lax = TypeAdapter(float).validate_python("1.5")  # 1.5 outside strict mode
```

[`RootModel`, `Json[T]`][pydantic:json] → root value as a model; JSON text embedded in a field

```py
class Symbols(RootModel[list[str]]):
    model_config = ConfigDict(frozen=True)


symbols = Symbols.model_validate_json(b'["A","B"]').root  # list[str]


class Envelope(BaseModel):
    payload: Json[list[int]]  # validates a JSON string, yields list[int]


envelope = Envelope(payload="[1, 2]")
```

[`field_serializer`, `PlainSerializer`, `computed_field`, `Field(exclude=)`][pydantic:serialization] → output shape

```py
type Clock = Annotated[datetime, PlainSerializer(lambda v: v.isoformat(), return_type=str, when_used="json")]


class Row(BaseModel):
    at: Clock
    day: date
    secret: str = Field(exclude=True)  # never dumped
    total: int = 0

    @field_serializer("day")
    def dump_day(self, value: date) -> str:
        return f"{value:%d %b}"

    @computed_field(exclude_if=lambda value: value == 0)  # exclude_if on computed fields: 2.13
    @property
    def doubled(self) -> int:
        return self.total * 2


row = Row(at=datetime.now(), day=date.today(), secret="x", total=1)
row.model_dump(mode="json")  # JSON-safe primitives
row.model_dump(polymorphic_serialization=True)  # 2.13: subclass fields of nested models included
```

[`model_fields`, `model_json_schema`][pydantic:fields] → introspection without an instance

```py
fields: dict[str, FieldInfo] = Item.model_fields
info = fields["quantity"]
info.annotation  # int-based annotation, Annotated metadata stripped into info.metadata
info.validation_alias  # "qty"
info.is_required()  # True

names = tuple(Item.model_fields)
schema = Item.model_json_schema()
```

## refs

[pydantic:docs]: https://docs.pydantic.dev/2.13/

[pydantic:fields]: https://pydantic.dev/docs/validation/2.13/concepts/fields/
    The alias parameter is used for both validation and serialization.

[pydantic:alias]: https://pydantic.dev/docs/validation/2.13/concepts/alias/
    The alias is prioritized.

[pydantic:config]: https://pydantic.dev/docs/validation/2.13/api/pydantic/config/

[pydantic:validators]: https://pydantic.dev/docs/validation/2.13/concepts/validators/

[pydantic:type-adapter]: https://pydantic.dev/docs/validation/2.13/concepts/type_adapter/

[pydantic:unions]: https://pydantic.dev/docs/validation/2.13/concepts/unions/
    in Pydantic >=2 the default mode for Union validation is union_mode='smart'.

[pydantic:strict]: https://pydantic.dev/docs/validation/2.13/concepts/strict_mode/

[pydantic:json]: https://pydantic.dev/docs/validation/2.13/concepts/json/

[pydantic:serialization]: https://pydantic.dev/docs/validation/2.13/concepts/serialization/

[pydantic:models]: https://pydantic.dev/docs/validation/2.13/concepts/models/
    model_construct() : Creates models without running validation.

[pydantic:changelog]: https://pydantic.dev/docs/validation/2.13/get-started/changelog/
    Track extra fields set after init in `model_fields_set`

[pydantic:release]: https://pydantic.dev/articles/pydantic-v2-13-release
