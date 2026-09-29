# [pydantic settings][pydantic-settings:docs]

2.15.0 · Python 3.12+ syntax

```py
import enum
from typing import Annotated, Literal

from pydantic import AliasChoices, BaseModel, BeforeValidator, Field, SecretStr
from pydantic_settings import (
    BaseSettings, CliApp, CliSubCommand, ForceDecode, NoDecode,
    PydanticBaseSettingsSource, SettingsConfigDict, TomlConfigSettingsSource,
)
```

## config flags

```py
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_",  # variable names only; aliases bypass it
        env_nested_delimiter="__",  # APP_DB__HOST → db.host
        env_nested_max_split=None,  # int limits the split depth
        env_parse_none_str="none",  # this env string becomes None
        env_parse_enums=True,  # env value names the member, not its value
        env_ignore_empty=True,  # empty variable → field default
        case_sensitive=False,
        nested_model_default_partial_update=True,  # env patches a nested default
        extra="ignore",  # unknown variables and files are dropped
        frozen=True,
    )
```

## nested models from env

```py
class Timeout(BaseModel):
    connect: float
    read: float


class Db(BaseModel):
    url: str
    timeout: Timeout
    retries: tuple[int, int, int]  # JSON array
    limit: float | None  # "none" → None
    tags: dict[str, bool]  # JSON object


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_", env_nested_delimiter="__", env_parse_none_str="none"
    )
    db: Db


# APP_DB__URL=postgres://h/db  APP_DB__TIMEOUT__CONNECT=2.0  APP_DB__TIMEOUT__READ=10
# APP_DB__RETRIES='[1, 2, 4]'  APP_DB__LIMIT=none  APP_DB__TAGS='{"a": true}'
settings = Settings()
```

## enum and literal coercion

```py
class Level(enum.Enum):
    LOW = "l"
    HIGH = "h"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_parse_enums=True)
    level: Level  # LEVEL=HIGH → Level.HIGH (member name)
    mode: Literal["dev", "prod"]  # MODE=prod; checked by validation
```

## delimited lists

```py
def split(value: object) -> object:
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return value


type Names = Annotated[list[str], NoDecode, BeforeValidator(split), Field(min_length=1)]


class Settings(BaseSettings):
    names: Names  # NAMES=alice,bob → ["alice", "bob"]; NoDecode skips json.loads
    raw: Annotated[list[int], ForceDecode]  # RAW='[1, 2]'; wins over enable_decoding=False
```

## aliases

```py
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_")
    host: str = Field(validation_alias=AliasChoices("DATABASE_HOST", "DB_HOST"))
    mode: str = Field(validation_alias="DEPLOY_ENV")  # reads DEPLOY_ENV as written
    port: int  # APP_PORT


# env_prefix_target="all" also prefixes aliases; "alias" prefixes only aliases
```

## secrets

```py
class Settings(BaseSettings):
    model_config = SettingsConfigDict(secrets_dir="/run/secrets")  # file name = field name
    token: Annotated[SecretStr, Field(min_length=32)]


settings = Settings()
settings.token  # SecretStr('**********'); repr and logs stay masked
settings.token.get_secret_value()
```

## TOML source

```py
class Settings(BaseSettings):
    model_config = SettingsConfigDict(toml_file="config.toml", extra="ignore")
    name: str
    secrets: str

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # earlier entries win; toml_table_header picks one table of the file
        return (
            init_settings,
            env_settings,
            TomlConfigSettingsSource(settings_cls, toml_table_header=("vars",)),
        )
```

## CLI source

```py
class Serve(BaseSettings):
    port: int = 8000

    def cli_cmd(self) -> None:
        run(self.port)


class Root(BaseSettings):
    model_config = SettingsConfigDict(cli_implicit_flags=True)  # bool → --verbose/--no-verbose
    verbose: bool = False
    serve: CliSubCommand[Serve]

    def cli_cmd(self) -> None:
        CliApp.run_subcommand(self)  # dispatches to the chosen subcommand's cli_cmd


# without implicit flags a bool option consumes the next token as its value
# argv: prog --verbose serve --port 9000; CLI outranks init and env values
CliApp.run(Root, cli_args=["--verbose", "serve", "--port", "9000"])
```

## refs

[pydantic-settings:docs]: https://github.com/pydantic/pydantic-settings/blob/v2.15.0/docs/index.md
    default values of `BaseSettings` fields are validated by default
    Pydantic settings consider `extra` config in case of dotenv file.

[pydantic-settings:nested]: https://github.com/pydantic/pydantic-settings/blob/v2.15.0/docs/index.md#parsing-environment-variable-values
    By default environment variables are parsed verbatim, including if the value is empty.

[pydantic-settings:decoding]: https://github.com/pydantic/pydantic-settings/blob/v2.15.0/docs/index.md#disabling-json-parsing
    The `NoDecode` annotation disables JSON parsing for the `numbers` field.

[pydantic-settings:priority]: https://github.com/pydantic/pydantic-settings/blob/v2.15.0/docs/index.md#field-value-priority

[pydantic-settings:toml]: https://github.com/pydantic/pydantic-settings/blob/v2.15.0/docs/index.md#other-settings-source
    The files are merged shallowly in increasing order of priority.

[pydantic-settings:cli]: https://github.com/pydantic/pydantic-settings/blob/v2.15.0/docs/index.md#command-line-support
