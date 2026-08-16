from typing import Any

import httpx


PAPER_API_URL = "https://paper-api.alpaca.markets"
ACCOUNT_FIELDS = (
    "status",
    "currency",
    "cash",
    "portfolio_value",
    "equity",
    "last_equity",
    "buying_power",
    "daytrade_count",
)
POSITION_FIELDS = (
    "symbol",
    "side",
    "qty",
    "avg_entry_price",
    "market_value",
    "current_price",
    "unrealized_pl",
)
ORDER_FIELDS = (
    "id",
    "symbol",
    "side",
    "type",
    "qty",
    "filled_qty",
    "status",
    "submitted_at",
)
FILL_FIELDS = (
    "id",
    "order_id",
    "symbol",
    "side",
    "qty",
    "price",
    "transaction_time",
)


class AlpacaReadError(RuntimeError):
    pass


class AlpacaTimeoutError(AlpacaReadError):
    pass


class AlpacaRateError(AlpacaReadError):
    def __init__(self, retry_after: str) -> None:
        super().__init__("Alpaca read limit was reached")
        self.retry_after = retry_after


def select_fields(payload: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    return {field: payload.get(field) for field in fields}


def decimal_string(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, int | float) and not isinstance(value, bool):
        return str(value)
    raise AlpacaReadError("Alpaca portfolio history was invalid")


def _object(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise AlpacaReadError("Alpaca response was invalid")
    return payload


def _objects(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
        raise AlpacaReadError("Alpaca response was invalid")
    return payload


class AlpacaReadClient:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def account(self) -> dict[str, Any]:
        payload = _object(await self._get("/v2/account"))
        return select_fields(payload, ACCOUNT_FIELDS)

    async def positions(self) -> list[dict[str, Any]]:
        payload = _objects(await self._get("/v2/positions"))
        return [select_fields(item, POSITION_FIELDS) for item in payload]

    async def orders(
        self,
        status: str,
        limit: int,
        before_order_id: str | None = None,
    ) -> list[dict[str, Any]]:
        payload = _objects(
            await self._get(
                "/v2/orders",
                {
                    "status": status,
                    "limit": limit,
                    "direction": "desc",
                    "nested": "true",
                    "before_order_id": before_order_id,
                },
            )
        )
        return [select_fields(item, ORDER_FIELDS) for item in payload]

    async def fills(
        self,
        limit: int,
        page_token: str | None = None,
    ) -> list[dict[str, Any]]:
        payload = _objects(
            await self._get(
                "/v2/account/activities",
                {
                    "activity_types": "FILL",
                    "direction": "desc",
                    "page_size": limit,
                    "page_token": page_token,
                },
            )
        )
        return [select_fields(item, FILL_FIELDS) for item in payload]

    async def equity(self, period: str, timeframe: str) -> dict[str, Any]:
        params = {"period": period, "timeframe": timeframe}
        if timeframe != "1D":
            params["intraday_reporting"] = "market_hours"
        payload = _object(await self._get("/v2/account/portfolio/history", params))
        timestamps = payload.get("timestamp", [])
        equity = payload.get("equity", [])
        profit_loss = payload.get("profit_loss", [])
        if not all(isinstance(values, list) for values in (timestamps, equity, profit_loss)):
            raise AlpacaReadError("Alpaca portfolio history was invalid")
        try:
            points = [
                {
                    "timestamp": timestamp,
                    "equity": decimal_string(equity_value),
                    "profit_loss": decimal_string(profit_loss_value),
                }
                for timestamp, equity_value, profit_loss_value in zip(
                    timestamps,
                    equity,
                    profit_loss,
                    strict=True,
                )
            ]
        except ValueError as error:
            raise AlpacaReadError("Alpaca portfolio history was invalid") from error
        return {"points": points}

    async def _get(self, path: str, params: dict[str, object] | None = None) -> Any:
        query = {key: value for key, value in (params or {}).items() if value is not None}
        try:
            response = await self._client.get(path, params=query)
        except httpx.TimeoutException as error:
            raise AlpacaTimeoutError("Alpaca read timed out") from error
        except httpx.RequestError as error:
            raise AlpacaReadError("Alpaca read failed") from error
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After", "60")[:40]
            raise AlpacaRateError(retry_after)
        try:
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise AlpacaReadError("Alpaca read failed") from error
