from datetime import date
from operator import attrgetter

import httpx2
from pydantic import Field, TypeAdapter

from mt.rules.shared import settings

from .http import Payload, http_timeout


API_URL = "https://finnhub.io/api/v1"
COMMON_STOCK = "Common Stock"
CLIENT = httpx2.Client(
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
    industry: str = Field(alias="finnhubIndustry", default="")


class _Calendar(Payload):
    releases: list[Release] = Field(alias="earningsCalendar")


stocks_adapter = TypeAdapter(list[Stock])


def stocks() -> frozenset[str]:
    payload = stocks_adapter.validate_json(
        CLIENT.get("/stock/symbol", params={"exchange": "US"}).raise_for_status().content
    )
    return frozenset(stock.symbol for stock in payload if stock.type == COMMON_STOCK)


def profile(symbol: str) -> Profile:
    return Profile.model_validate_json(
        CLIENT.get("/stock/profile2", params={"symbol": symbol}).raise_for_status().content
    )


def earnings_dates(start: date, end: date) -> dict[str, date]:
    calendar = _Calendar.model_validate_json(
        CLIENT.get("/calendar/earnings", params={"from": start.isoformat(), "to": end.isoformat()})
        .raise_for_status()
        .content
    )
    return {
        release.symbol: release.date
        for release in sorted(calendar.releases, key=attrgetter("date"), reverse=True)
    }
