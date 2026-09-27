# [pydantic][pydantic:docs]

2.12.5 · pydantic-core 2.41.5 · Python 3.12+ syntax

```py
from datetime import datetime
from typing import Annotated, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    TypeAdapter,
    computed_field,
    model_validator,
)
from pydantic.fields import FieldInfo
```

[`Field(...)`][pydantic:fields] → `FieldInfo`; constraints, factories, and aliases configure validation and serialization.

```py
type PositiveRatio = Annotated[float, Field(gt=0, le=1)]
type Identifier = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[a-z_]+$")]


class Item(BaseModel):
    name: Identifier
    ratio: PositiveRatio
    quantity: int = Field(ge=0, validation_alias="qty")
    tags: list[str] = Field(default_factory=list)


item = Item(name="sample", ratio=0.5, qty=2)
```

[`BeforeValidator(func)` / `AfterValidator(func)`][pydantic:validators] → annotation metadata

```py
def parse_none(value: object) -> object:
    return None if value == "none" else value  # raw input, before coercion


def check_even(value: int) -> int:
    if value % 2:
        raise ValueError("value must be even")
    return value  # validated int, after coercion


type OptionalRatio = Annotated[PositiveRatio | None, BeforeValidator(parse_none)]
type EvenNumber = Annotated[int, AfterValidator(check_even)]


class Model(BaseModel):
    ratio: OptionalRatio
    count: EvenNumber


model = Model(ratio="none", count="2")
```

[`ConfigDict(extra, frozen, strict, validate_by_name, validate_by_alias)`][pydantic:config] → `ConfigDict`

```py
class Model(BaseModel):
    model_config = ConfigDict(
        extra="forbid",  # unknown inputs fail; "ignore" drops them
        frozen=True,  # blocks attribute assignment
        strict=True,  # rejects "1" for an int field
        validate_by_name=True,
        validate_by_alias=True,
    )
    value: int = Field(alias="input", serialization_alias="value")


model = Model(input=1)
model = Model(value=1)
model.model_dump(by_alias=True)  # {"value": 1}
```

[`model_validator(mode: Literal['after'])`][pydantic:validators] → decorator

```py
class Span(BaseModel):
    start: datetime
    end: datetime

    @model_validator(mode="after")
    def check_order(self) -> Self:
        if self.end <= self.start:
            raise ValueError("end must follow start")
        return self


span = Span.model_validate({"start": "2026-01-01", "end": "2026-01-02"})
```

[`computed_field`][pydantic:fields] → decorator

```py
class Rectangle(BaseModel):
    width: float = Field(gt=0)
    height: float = Field(gt=0)

    @computed_field
    @property
    def area(self) -> float:
        return self.width * self.height


rectangle = Rectangle(width=2, height=3)
rectangle.model_dump()  # {"width": 2.0, "height": 3.0, "area": 6.0}
```

[`TypeAdapter(type)`][pydantic:type-adapter] → `TypeAdapter[T]`

```py
# Construct once; reuse the compiled schema for subsequent validations.
items_adapter: TypeAdapter[list[Item]] = TypeAdapter(list[Item])
items = items_adapter.validate_python([
    {"name": "sample", "ratio": 0.5, "qty": "2"},
])
items = items_adapter.validate_json(
    b'[{"name":"sample","ratio":0.5,"qty":2}]'
)
```

[`model_validate(obj)` / `model_validate_json(data)`][pydantic:models] → `Self`

```py
class User(BaseModel):
    id: int
    name: str


user = User.model_validate({"id": "1", "name": "Ada"})
user = User.model_validate_json(b'{"id":1,"name":"Ada"}')
# Invalid input raises ValidationError with structured failure details.
```

[`model_dump` / `model_dump_json` / `model_copy`][pydantic:models] → `dict` / `str` / `Self`; copying is shallow by default.

```py
record = user.model_dump()  # {"id": 1, "name": "Ada"}
body = user.model_dump_json()  # JSON str
copy = user.model_copy(deep=True)
renamed = user.model_copy(update={"name": "Grace"})  # trusted update: no validation

# Revalidate when the update is untrusted.
validated = User.model_validate({**user.model_dump(), "name": "Grace"})
```

[`model_fields`][pydantic:fields] → `dict[str, FieldInfo]`

```py
fields: dict[str, FieldInfo] = Item.model_fields
info = fields["quantity"]
info.annotation  # int
info.validation_alias  # "qty"
info.is_required()  # True

names = tuple(Item.model_fields)  # declared fields, without serializing an instance
schema = Item.model_json_schema()  # nested schema and constraints
```

## refs

[pydantic:docs]: https://docs.pydantic.dev/2.12/

[pydantic:fields]: https://pydantic.dev/docs/validation/2.12/concepts/fields/
    The alias parameter is used for both validation and serialization.

[pydantic:validators]: https://pydantic.dev/docs/validation/2.12/concepts/validators/

[pydantic:config]: https://pydantic.dev/docs/validation/2.12/api/pydantic/config/

[pydantic:type-adapter]: https://pydantic.dev/docs/validation/2.12/concepts/type_adapter/

[pydantic:models]: https://pydantic.dev/docs/validation/2.12/concepts/models/
