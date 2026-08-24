from typing import Any, cast

import httpx
from alpaca.common.enums import BaseURL

from bot.attribution import find_order_strategy_label


type JsonRow = dict[str, Any]


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
