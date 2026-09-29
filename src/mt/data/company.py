from datetime import date
from functools import lru_cache

import httpx2
from pydantic import ValidationError

from mt.rules.shared import settings

from .asset import Asset, AssetType
from .finnhub import Profile, profile


def is_large_enough(asset: Asset, market_cap_usd_min: float, session_on: date) -> bool:
    if asset.asset_type != AssetType.STOCK:
        return False
    found = _try_profile(asset.symbol, session_on)
    return found is not None and found.market_cap_musd * 1_000_000 >= market_cap_usd_min


@lru_cache(maxsize=settings.company.profile_cache_max)
def _profile(symbol: str, session_on: date) -> Profile:
    return profile(symbol)


def _try_profile(symbol: str, session_on: date) -> Profile | None:
    try:
        return _profile(symbol, session_on)
    except httpx2.HTTPError, ValidationError:
        return None
