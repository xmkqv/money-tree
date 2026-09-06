from datetime import date

import httpx
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from mt.config.settings import settings

from .http import http_timeout


API_URL = "https://finnhub.io/api/v1"
COMMON_STOCK = "Common Stock"
TIMEOUT = http_timeout(settings.finnhub.timeout)


class _Payload(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


class Listing(_Payload):
    symbol: str
    type: str


class Release(_Payload):
    symbol: str
    date: date


class _Calendar(_Payload):
    releases: list[Release] = Field(alias="earningsCalendar")


listings_adapter = TypeAdapter(list[Listing])


def stocks() -> frozenset[str]:
    payload = _get("/stock/symbol", {"exchange": "US"})
    listings = listings_adapter.validate_python(payload)
    return frozenset(listing.symbol for listing in listings if listing.type == COMMON_STOCK)


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
    token = settings.finnhub.api_key.get_secret_value()
    with httpx.Client(base_url=API_URL, timeout=TIMEOUT) as client:
        response = client.get(path, params=params, headers={"X-Finnhub-Token": token})
        response.raise_for_status()
        return response.json()
