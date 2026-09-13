from datetime import date, timedelta
from functools import lru_cache

from mt.exchange import XNYS
from mt.rules.shared import settings

from .asset import Asset, AssetType
from .finnhub import earnings_dates


@lru_cache(maxsize=settings.earnings.calendar_cache_max)
def _calendar(day: date) -> dict[str, date]:
    return earnings_dates(day, day + timedelta(days=settings.earnings.block_days))


def is_earnings_blocked(asset: Asset, day: date) -> bool:
    return asset.asset_type == AssetType.STOCK and asset.symbol in _calendar(day)


def is_earnings_exit_due(asset: Asset, day: date) -> bool:
    if asset.asset_type != AssetType.STOCK:
        return False
    upcoming = _calendar(day).get(asset.symbol)
    if upcoming is None:
        return False
    session = XNYS.date_to_session(upcoming, direction="next")
    return day == XNYS.previous_session(session).date()
