from datetime import date, timedelta
from functools import lru_cache

from mt.exchange import previous_session_on
from mt.rules.shared import settings

from .asset import Asset, AssetType
from .finnhub import earnings_dates


def is_earnings_blocked(asset: Asset, session_on: date) -> bool:
    return asset.asset_type == AssetType.STOCK and asset.symbol in _calendar(session_on)


def is_earnings_exit_due(asset: Asset, session_on: date) -> bool:
    if asset.asset_type != AssetType.STOCK:
        return False
    event_on = _calendar(session_on).get(asset.symbol)
    if event_on is None:
        return False
    return previous_session_on(event_on) <= session_on <= event_on


@lru_cache(maxsize=settings.calendar.cache_max)
def _calendar(session_on: date) -> dict[str, date]:
    return earnings_dates(session_on, session_on + timedelta(days=settings.earnings.block_days))
