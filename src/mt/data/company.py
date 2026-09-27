from datetime import date
from functools import lru_cache

from mt.rules.shared import settings

from .asset import Asset, AssetType
from .finnhub import Profile, profile


@lru_cache(maxsize=settings.company.profile_cache_max)
def _profile(symbol: str, day: date) -> Profile:
    return profile(symbol)


def is_large_enough(asset: Asset, minimum: float, day: date) -> bool:
    if asset.asset_type != AssetType.STOCK:
        return False
    return _profile(asset.symbol, day).market_cap_musd * 1_000_000 >= minimum


def industry(asset: Asset, day: date) -> str:
    return _profile(asset.symbol, day).industry if asset.asset_type == AssetType.STOCK else ""
