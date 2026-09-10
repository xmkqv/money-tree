# pydantic-settings

2.15.0 · Python 3.12+ syntax

```python
from typing import Annotated

from pydantic import AliasChoices, BaseModel, BeforeValidator, Field
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
```

[`BaseSettings()`][settings] → settings instance

```python
class Settings(BaseSettings):
    host: str
    port: int


# Environment: HOST=localhost PORT=5432
settings = Settings()
settings.host  # "localhost"
settings.port  # 5432

# Initializer values override environment values by default.
overridden = Settings(host="db.example.com", port=5433)
```

[`SettingsConfigDict(env_nested_delimiter, env_prefix, extra, frozen)`][settings] → `SettingsConfigDict`

```python
class Database(BaseModel):
    host: str
    port: int


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        env_prefix="APP_",
        extra="ignore",
        frozen=True,
    )
    database: Database


# Environment: APP_DATABASE__HOST=localhost APP_DATABASE__PORT=5432
settings = Settings()
settings.database.host  # "localhost"
settings.database.port  # 5432
```

[`Field(validation_alias=...)`][settings] → `FieldInfo`

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_")
    host: str = Field(validation_alias=AliasChoices("DATABASE_HOST", "DB_HOST"))
    port: int


# Environment: DATABASE_HOST=localhost APP_PORT=5432
settings = Settings()
settings.host  # "localhost"; alias bypasses env_prefix by default
settings.port  # 5432
```

[`NoDecode`][settings] → annotation metadata

```python
def split_values(value: object) -> object:
    if isinstance(value, str):
        return [part.strip() for part in value.split(",")]
    return value


type Names = Annotated[
    list[Annotated[str, Field(min_length=1)]],
    BeforeValidator(split_values),
    Field(min_length=1),
]


class Settings(BaseSettings):
    names: Annotated[Names, NoDecode]


# Environment: NAMES=alice,bob
settings = Settings()
settings.names  # ["alice", "bob"]
```

## tips

- Missing required settings raise `ValidationError` during construction.
- Defaults are validated; `validate_default=False` disables this.
- Nested settings models inherit `BaseModel`; delimiters support multiple nesting levels.
- Nested environment values override values from the corresponding top-level JSON variable.
- Unrelated environment variables are ignored; `extra` also governs loaded dotenv entries.
- Complex fields use JSON decoding by default; `NoDecode` permits a custom input format.
- `ForceDecode` enables field JSON parsing when `enable_decoding=False`.

## refs

[settings]: https://github.com/pydantic/pydantic-settings/blob/v2.15.0/docs/index.md
