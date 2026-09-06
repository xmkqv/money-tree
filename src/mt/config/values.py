from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, SecretStr


def parse_none(value: object) -> object:
    return None if value == "none" else value


type Count = Annotated[int, Field(gt=0)]
type Amount = Annotated[float, Field(gt=0)]
type Fraction = Annotated[float, Field(gt=0, le=1)]
type OptionalFraction = Annotated[Fraction | None, BeforeValidator(parse_none)]
type MaxAge = Annotated[int, Field(ge=0)]
type Symbol = Annotated[str, Field(min_length=1, max_length=12, pattern=r"^[A-Z][A-Z.]*$")]
type RequiredSecret = Annotated[SecretStr, Field(min_length=1)]
type SigningSecret = Annotated[SecretStr, Field(min_length=32)]
type Mode = Literal["development", "production"]
type BrokerMode = Literal["live", "paper"]
type DataFeedName = Literal["sip", "delayed_sip", "iex"]


class SettingsSection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
