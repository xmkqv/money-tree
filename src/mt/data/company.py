from datetime import date
from functools import lru_cache

import httpx
from pydantic import ValidationError

from mt.rules.shared import settings

from .asset import Asset, AssetType
from .finnhub import Profile, profile


@lru_cache(maxsize=settings.company.profile_cache_max)
def _profile(symbol: str, day: date) -> Profile:
    return profile(symbol)


def _try_profile(symbol: str, day: date) -> Profile | None:
    try:
        return _profile(symbol, day)
    except (httpx.HTTPError, ValidationError):
        return None


def is_large_enough(asset: Asset, minimum: float, day: date) -> bool:
    if asset.asset_type != AssetType.STOCK:
        return False
    found = _try_profile(asset.symbol, day)
    return found is not None and found.market_cap_musd * 1_000_000 >= minimum
