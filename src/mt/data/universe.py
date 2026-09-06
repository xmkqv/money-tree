import json
from importlib import import_module
from typing import Any, cast
from uuid import uuid4

from mt.config.settings import settings


yfinance = cast(Any, import_module("yfinance"))


class LoadUniverseError(Exception):
    pass


def eligible(listing: frozenset[str]) -> list[str]:
    try:
        symbols = screen(listing)
        write_cache(symbols)
        return symbols
    except Exception as screen_error:
        try:
            return read_cache()
        except Exception as cache_error:
            message = (
                f"the screen failed with {type(screen_error).__name__}; "
                f"cache {settings.universe.cache} failed with {type(cache_error).__name__}"
            )
            raise LoadUniverseError(message) from ExceptionGroup(
                "universe loading failed",
                [screen_error, cache_error],
            )


def screen(listing: frozenset[str]) -> list[str]:
    Query = yfinance.EquityQuery
    query = Query(
        "and",
        [
            Query("eq", ["region", "us"]),
            Query("gte", ["intradaymarketcap", settings.universe.market_cap_usd_min]),
        ],
    )
    quotes: list[dict[str, Any]] = []
    offset = 0
    while True:
        page = yfinance.screen(
            query,
            offset=offset,
            size=250,
            sortField="intradaymarketcap",
            sortAsc=False,
        )
        values = cast(list[dict[str, Any]], page.get("quotes", []))
        quotes.extend(values)
        offset += len(values)
        if not values or offset >= int(page.get("total", offset)):
            break
    rows = [
        (
            str(value.get("symbol", "")).replace("-", "."),
            float(value.get("marketCap") or 0),
            float(value.get("averageDailyVolume3Month") or 0),
            float(value.get("regularMarketPrice") or 0),
        )
        for value in quotes
        if value.get("quoteType") == "EQUITY"
    ]
    return sorted(
        {
            symbol
            for symbol, cap, volume, price in rows
            if symbol in listing
            and cap >= settings.universe.market_cap_usd_min
            and price >= settings.universe.price_usd_min
            and volume * price >= settings.universe.turnover_usd_min
        }
    )


def read_cache() -> list[str]:
    cached: object = json.loads(settings.universe.cache.read_text())
    if not isinstance(cached, dict):
        raise ValueError("universe cache must be an eligible-symbol object")
    payload = cast(dict[str, object], cached)
    if set(payload) != {"eligible"}:
        raise ValueError("universe cache must be an eligible-symbol object")
    symbols = payload["eligible"]
    if not isinstance(symbols, list):
        raise ValueError("universe cache eligible symbols must be non-empty strings")
    loaded: set[str] = set()
    for symbol in cast(list[object], symbols):
        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("universe cache eligible symbols must be non-empty strings")
        loaded.add(symbol.strip())
    return sorted(loaded)


def write_cache(symbols: list[str]) -> None:
    cache = settings.universe.cache
    cache.parent.mkdir(parents=True, exist_ok=True)
    temporary = cache.with_name(f".{cache.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps({"eligible": symbols}))
        temporary.replace(cache)
    finally:
        temporary.unlink(missing_ok=True)
