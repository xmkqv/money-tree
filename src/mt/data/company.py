from datetime import date
from functools import lru_cache

from mt.rules.shared import settings

from .asset import Asset, AssetType
from .finnhub import market_cap_usd


@lru_cache(maxsize=settings.company.profile_cache_max)
def _market_cap_usd(symbol: str, day: date) -> float:
    return market_cap_usd(symbol)


def is_large_enough(asset: Asset, minimum: float, day: date) -> bool:
    if asset.asset_type != AssetType.STOCK:
        return False
    return _market_cap_usd(asset.symbol, day) >= minimum
