from datetime import date, timedelta
from functools import lru_cache

import httpx2
from pydantic import Field, TypeAdapter

from mt.exchange import upcoming_session_on
from mt.rules.shared import settings

from .http import Payload, http_timeout


class Stock(Payload):
    symbol: str
    type: str


class Release(Payload):
    symbol: str
    date: date
    hour: str = ""


class Profile(Payload):
    market_cap_musd: float = Field(alias="marketCapitalization", default=0.0)


class _Calendar(Payload):
    releases: list[Release] = Field(alias="earningsCalendar")


API_URL = "https://finnhub.io/api/v1"
COMMON_STOCK = "Common Stock"
AFTER_CLOSE = "amc"

_stocks_adapter = TypeAdapter(list[Stock])


def stocks() -> frozenset[str]:
    payload = _stocks_adapter.validate_json(
        _client().get("/stock/symbol", params={"exchange": "US"}).raise_for_status().content
    )
    return frozenset(stock.symbol for stock in payload if stock.type == COMMON_STOCK)


def profile(symbol: str) -> Profile:
    return Profile.model_validate_json(
        _client().get("/stock/profile2", params={"symbol": symbol}).raise_for_status().content
    )


def earnings_dates(start: date, end: date) -> dict[str, date]:
    calendar = _Calendar.model_validate_json(
        _client()
        .get("/calendar/earnings", params={"from": start.isoformat(), "to": end.isoformat()})
        .raise_for_status()
        .content
    )
    events = sorted(
        ((_event_on(release), release.symbol) for release in calendar.releases), reverse=True
    )
    return {symbol: event_on for event_on, symbol in events}


@lru_cache(maxsize=1)
def _client() -> httpx2.Client:
    return httpx2.Client(
        base_url=API_URL,
        timeout=http_timeout(settings.finnhub.timeout),
        follow_redirects=True,
        headers={"X-Finnhub-Token": settings.finnhub.api_key.get_secret_value()},
    )


def _event_on(release: Release) -> date:
    is_after_close = release.hour == AFTER_CLOSE
    return upcoming_session_on(release.date + timedelta(days=1 if is_after_close else 0))
