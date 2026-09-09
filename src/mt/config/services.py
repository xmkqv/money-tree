from collections.abc import Iterator
from tomllib import loads
from typing import Literal

from pydantic import BaseModel
from pydantic_settings import BaseSettings

from .settings import BotSettings, DeploymentSettings, LoginSettings, WebSettings


type ServiceName = Literal["web", "bot"]

SERVICE_SETTINGS: dict[ServiceName, tuple[type[BaseSettings], ...]] = {
    "web": (WebSettings, LoginSettings),
    "bot": (BotSettings,),
}


def secret_keys() -> set[str]:
    configuration = DeploymentSettings()  # pyright: ignore[reportCallIssue]
    path = configuration.project_root / f"mise.{configuration.mode}.toml"
    declared: dict[str, str] = loads(path.read_text())["vars"]
    return set(declared["secrets"].split())


def iter_keys(model: type[BaseModel], prefix: str) -> Iterator[str]:
    for name, field in model.model_fields.items():
        annotation = field.annotation
        if isinstance(field.validation_alias, str):
            yield field.validation_alias
        elif isinstance(annotation, type) and issubclass(annotation, BaseModel):
            yield from iter_keys(annotation, f"{prefix}{name.upper()}__")
        else:
            yield f"{prefix}{name.upper()}"


def service_secrets(service: ServiceName) -> list[str]:
    read = {key for model in SERVICE_SETTINGS[service] for key in iter_keys(model, "")}
    return sorted(secret_keys() & read)
