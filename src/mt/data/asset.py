from datetime import date
from typing import Any, Self, cast

from lumibot.entities.asset import Asset as LumibotAsset
from lumibot.tools import create_options_symbol
from pydantic import BaseModel, model_validator


AssetType = LumibotAsset.AssetType
OptionRight = LumibotAsset.OptionRight


class Asset(BaseModel, frozen=True, extra="forbid"):
    symbol: str
    asset_type: AssetType = AssetType.STOCK
    expiration: date | None = None
    strike: float = 0.0
    right: OptionRight | None = None
    multiplier: int = 1
    leverage: int = 1
    precision: str | None = None
    underlying_asset: Asset | None = None

    @classmethod
    def from_symbol(cls, symbol: str) -> Asset:
        symbol = symbol.strip().upper()
        if not symbol:
            raise ValueError("asset symbol must not be empty")
        base, separator, quote = symbol.partition("/")
        if separator and (not base or not quote or "/" in quote):
            raise ValueError("crypto symbols require a base and quote currency")
        if quote:
            return cls(symbol=base, asset_type=AssetType.CRYPTO, precision=quote)
        return cls.from_lumibot(LumibotAsset.symbol2asset(symbol))

    @classmethod
    def from_lumibot(cls, asset: LumibotAsset) -> Asset:
        return cls.model_validate(asset.to_dict())

    def to_lumibot(self) -> LumibotAsset:
        return LumibotAsset.from_dict(  # pyright: ignore[reportUnknownMemberType]
            self.model_dump(mode="json")
        )

    @model_validator(mode="after")
    def check_kind(self) -> Self:
        if self.asset_type == AssetType.CRYPTO and not self.precision:
            raise ValueError("crypto assets require a quote currency")
        if self.asset_type == AssetType.OPTION and (self.expiration is None or self.right is None):
            raise ValueError("option assets require expiration and right")
        return self

    def __str__(self) -> str:
        if self.asset_type == AssetType.CRYPTO:
            return f"{self.symbol}/{self.precision}"
        if self.asset_type == AssetType.OPTION:
            return str(
                cast(Any, create_options_symbol)(
                    self.symbol, self.expiration, self.right, self.strike
                )
            )
        return self.symbol
