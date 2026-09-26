from datetime import date

import httpx
from pydantic import Field, TypeAdapter

from mt.rules.shared import settings

from .http import Payload, http_timeout


API_URL = "https://finnhub.io/api/v1"
COMMON_STOCK = "Common Stock"
CLIENT = httpx.Client(
    base_url=API_URL,
    timeout=http_timeout(settings.finnhub.timeout),
    follow_redirects=True,
    headers={"X-Finnhub-Token": settings.finnhub.api_key.get_secret_value()},
)


class Stock(Payload):
    symbol: str
    type: str


class Release(Payload):
    symbol: str
    date: date


class Profile(Payload):
    market_cap_musd: float = Field(alias="marketCapitalization", default=0.0)


class _Calendar(Payload):
    releases: list[Release] = Field(alias="earningsCalendar")


stocks_adapter = TypeAdapter(list[Stock])


def stocks() -> frozenset[str]:
    payload = stocks_adapter.validate_python(_get("/stock/symbol", {"exchange": "US"}))
    return frozenset(stock.symbol for stock in payload if stock.type == COMMON_STOCK)


def market_cap_usd(symbol: str) -> float:
    profile = Profile.model_validate(_get("/stock/profile2", {"symbol": symbol}))
    return profile.market_cap_musd * 1_000_000


def earnings_dates(start: date, end: date) -> dict[str, date]:
    payload = _get("/calendar/earnings", {"from": start.isoformat(), "to": end.isoformat()})
    calendar = _Calendar.model_validate(payload)
    dates: dict[str, date] = {}
    for release in calendar.releases:
        upcoming = dates.get(release.symbol)
        if upcoming is None or release.date < upcoming:
            dates[release.symbol] = release.date
    return dates


def _get(path: str, params: dict[str, str]) -> object:
    response = CLIENT.get(path, params=params)
    response.raise_for_status()
    return response.json()
