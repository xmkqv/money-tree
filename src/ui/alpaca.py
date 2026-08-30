from typing import Any, cast

import httpx
from alpaca.common.enums import BaseURL

from bot.attribution import find_order_strategy_label


type JsonRow = dict[str, Any]


DATA_API_URL = "https://data.alpaca.markets"
PAGE_LIMIT = 100
PAGES_MAX = 40


def alpaca_api_url(is_paper: bool) -> str:
    target = BaseURL.TRADING_PAPER if is_paper else BaseURL.TRADING_LIVE
    return target.value


class AlpacaReadClient:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def account(self) -> Any:
        return await self._get("/v2/account")

    async def positions(self) -> list[JsonRow]:
        positions = cast(list[JsonRow], await self._get("/v2/positions"))
        orders = await self.orders("all", 500)
        strategies: dict[str, str] = {}
        for order in orders:
            symbol = order.get("symbol")
            strategy = order["strategy"]
            if isinstance(symbol, str) and isinstance(strategy, str):
                strategies.setdefault(symbol, strategy)
        attributed: list[JsonRow] = []
        for position in positions:
            symbol = position.get("symbol")
            strategy = strategies.get(symbol) if isinstance(symbol, str) else None
            attributed.append({**position, "strategy": strategy})
        return attributed

    async def orders(self, status: str, limit: int, until: str | None = None) -> list[JsonRow]:
        orders = cast(
            list[JsonRow],
            await self._get(
                "/v2/orders",
                {"status": status, "limit": limit, "direction": "desc", "until": until},
            ),
        )
        return [
            {**order, "strategy": self._order_strategy(order.get("client_order_id"))}
            for order in orders
        ]

    async def fills(self, limit: int, page_token: str | None = None) -> list[JsonRow]:
        fills = cast(
            list[JsonRow],
            await self._get(
                "/v2/account/activities",
                {
                    "activity_types": "FILL",
                    "direction": "desc",
                    "page_size": limit,
                    "page_token": page_token,
                },
            ),
        )
        if not fills:
            return []
        newest_fill_at = max(cast(str, fill["transaction_time"]) for fill in fills)
        orders = await self.orders("all", 500, newest_fill_at)
        strategies = {
            str(order["id"]): strategy
            for order in orders
            if isinstance(strategy := order["strategy"], str)
        }
        return [{**fill, "strategy": strategies.get(str(fill.get("order_id")))} for fill in fills]

    async def clock(self) -> Any:
        return await self._get("/v2/clock")

    async def raw_fills(self, after: str | None = None) -> list[JsonRow]:
        """Fills as the broker reports them, paged, without per-page enrichment.

        `fills` attaches a strategy label by re-reading orders for every page,
        which doubles the request count. The ledger tags fills itself from a
        single order read, so it walks the raw endpoint instead.
        """
        collected: list[JsonRow] = []
        token: str | None = None
        for _ in range(PAGES_MAX):
            page = cast(
                list[JsonRow],
                await self._get(
                    "/v2/account/activities",
                    {
                        "activity_types": "FILL",
                        "direction": "desc",
                        "page_size": PAGE_LIMIT,
                        "page_token": token,
                        "after": after,
                    },
                ),
            )
            if not page:
                break
            collected.extend(page)
            token = str(page[-1]["id"])
            if len(page) < PAGE_LIMIT:
                break
        return collected

    async def raw_closed_orders(self, after: str | None = None) -> list[JsonRow]:
        """Closed orders, paged back by submission time, so fills can be tagged."""
        collected: list[JsonRow] = []
        seen: set[str] = set()
        until: str | None = None
        for _ in range(PAGES_MAX):
            page = cast(
                list[JsonRow],
                await self._get(
                    "/v2/orders",
                    {
                        "status": "closed",
                        "limit": PAGE_LIMIT,
                        "direction": "desc",
                        "until": until,
                        "after": after,
                    },
                ),
            )
            fresh = [order for order in page if str(order["id"]) not in seen]
            if not fresh:
                break
            collected.extend(fresh)
            seen.update(str(order["id"]) for order in fresh)
            until = str(page[-1]["submitted_at"])
            if len(page) < PAGE_LIMIT:
                break
        return collected

    async def equity(self, period: str, timeframe: str) -> dict[str, Any]:
        params: dict[str, object] = {"period": period, "timeframe": timeframe}
        if timeframe != "1D":
            params["intraday_reporting"] = "market_hours"
        history = await self._get("/v2/account/portfolio/history", params)
        points = [
            {"timestamp": timestamp, "equity": equity, "profit_loss": profit_loss}
            for timestamp, equity, profit_loss in zip(
                history["timestamp"], history["equity"], history["profit_loss"], strict=True
            )
        ]
        return {"points": points}

    async def _get(self, path: str, params: dict[str, object] | None = None) -> Any:
        query = {key: str(value) for key, value in (params or {}).items() if value is not None}
        response = await self._client.get(path, params=query)
        response.raise_for_status()
        return response.json()

    def _order_strategy(self, value: object) -> str | None:
        return find_order_strategy_label(value) if isinstance(value, str) else None


class AlpacaMarketDataClient:
    """Reads the market-data host, which is separate from the trading host."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def daily_bars(self, symbol: str, start: str) -> list[JsonRow]:
        return await self.bars(symbol, "1Day", start)

    async def bars(
        self,
        symbol: str,
        timeframe: str,
        start: str,
        end: str | None = None,
        limit: int = 1000,
    ) -> list[JsonRow]:
        """One page of bars. Callers bound the window, so no paging is needed."""
        params = {
            "timeframe": timeframe,
            "start": start,
            "limit": str(limit),
            "feed": "iex",
        }
        if end is not None:
            params["end"] = end
        return await self._page(symbol, params, pages_max=1)

    async def bars_paged(
        self,
        symbol: str,
        timeframe: str,
        start: str,
        end: str,
        limit: int = 1000,
        pages_max: int = 6,
    ) -> list[JsonRow]:
        """Bars across however many pages the window spans.

        Alpaca answers at most a page at a time whatever limit is asked for, so
        a window wider than one page comes back silently short — which on a
        chart reads as the data simply stopping partway.
        """
        params = {
            "timeframe": timeframe,
            "start": start,
            "end": end,
            "limit": str(limit),
            "feed": "iex",
        }
        return await self._page(symbol, params, pages_max=pages_max)

    async def _page(self, symbol: str, params: dict[str, str], pages_max: int) -> list[JsonRow]:
        rows: list[JsonRow] = []
        query = dict(params)
        for _ in range(pages_max):
            response = await self._client.get(f"/v2/stocks/{symbol}/bars", params=query)
            response.raise_for_status()
            payload = cast(dict[str, Any], response.json())
            rows.extend(cast(list[JsonRow], payload.get("bars") or []))
            token = payload.get("next_page_token")
            if not token:
                break
            query = {**params, "page_token": str(token)}
        return rows
