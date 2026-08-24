from typing import Any

import httpx
from alpaca.common.enums import BaseURL


def alpaca_api_url(is_paper: bool) -> str:
    target = BaseURL.TRADING_PAPER if is_paper else BaseURL.TRADING_LIVE
    return target.value


class AlpacaReadClient:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def account(self) -> Any:
        return await self._get("/v2/account")

    async def positions(self) -> Any:
        return await self._get("/v2/positions")

    async def orders(self, status: str, limit: int, until: str | None = None) -> Any:
        return await self._get(
            "/v2/orders", {"status": status, "limit": limit, "direction": "desc", "until": until}
        )

    async def fills(self, limit: int, page_token: str | None = None) -> Any:
        return await self._get(
            "/v2/account/activities",
            {
                "activity_types": "FILL",
                "direction": "desc",
                "page_size": limit,
                "page_token": page_token,
            },
        )

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
