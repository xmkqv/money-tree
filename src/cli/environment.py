from collections.abc import Iterator
from os import environ
from pathlib import Path
from tomllib import loads
from typing import Literal

from pydantic import BaseModel
from pydantic_settings import BaseSettings

from bot.config import BotSettings
from ui.config import LoginSettings, WebSettings


type ServiceName = Literal["web", "bot"]

SERVICE_SETTINGS: dict[ServiceName, tuple[type[BaseSettings], ...]] = {
    "web": (WebSettings, LoginSettings),
    "bot": (BotSettings,),
}


def declared_keys() -> set[str]:
    path = Path(environ["MISE_PROJECT_ROOT"]) / f"mise.{environ['MISE_ENV']}.toml"
    declared: dict[str, object] = loads(path.read_text())["env"]
    return {key for key, value in declared.items() if value == ""}


def read_keys(model: type[BaseModel], prefix: str) -> Iterator[str]:
    for name, field in model.model_fields.items():
        annotation = field.annotation
        if isinstance(field.validation_alias, str):
            yield field.validation_alias
        elif isinstance(annotation, type) and issubclass(annotation, BaseModel):
            yield from read_keys(annotation, f"{prefix}{name.upper()}__")
        else:
            yield f"{prefix}{name.upper()}"


def service_keys(service: ServiceName) -> list[str]:
    read = {key for model in SERVICE_SETTINGS[service] for key in read_keys(model, "")}
    return sorted(declared_keys() & read)
