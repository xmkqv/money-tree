from typing import Any

import httpx
from alpaca.common.enums import BaseURL
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from bot.types import BrokerMode


DATA_API_URL = "https://data.alpaca.markets"
PAGE_ROWS_MAX = 100
PAGES_MAX = 40


class _Payload(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


class Account(_Payload):
    account_number: str
    status: str
    equity: float
    last_equity: float
    cash: float
    buying_power: float


class Position(_Payload):
    symbol: str
    side: str
    qty: float
    avg_entry_price: float
    current_price: float
    market_value: float
    unrealized_pl: float
    unrealized_plpc: float


class Clock(_Payload):
    is_open: bool
    next_open: str


class Fill(_Payload):
    id: str
    order_id: str
    symbol: str
    side: str
    transaction_time: str
    qty: float
    price: float


class ClosedOrder(_Payload):
    id: str
    submitted_at: str
    client_order_id: str | None = None


class Bar(_Payload):
    at: str = Field(alias="t")
    open: float = Field(alias="o")
    high: float = Field(alias="h")
    low: float = Field(alias="l")
    close: float = Field(alias="c")
    volume: float = Field(alias="v", default=0.0)


class EquityPoint(_Payload):
    timestamp: int
    equity: float


class _PortfolioHistory(_Payload):
    timestamp: list[int]
    equity: list[float | None]


class _BarsPage(_Payload):
    bars: list[Bar] | None = None
    next_page_token: str | None = None


positions_adapter = TypeAdapter(list[Position])
fills_adapter = TypeAdapter(list[Fill])
closed_orders_adapter = TypeAdapter(list[ClosedOrder])


def alpaca_api_url(broker_mode: BrokerMode) -> str:
    target = BaseURL.TRADING_PAPER if broker_mode == "paper" else BaseURL.TRADING_LIVE
    return target.value


class AlpacaReadClient:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def account(self) -> Account:
        return Account.model_validate(await self._get("/v2/account"))

    async def raw_positions(self) -> list[Position]:
        return positions_adapter.validate_python(await self._get("/v2/positions"))

    async def clock(self) -> Clock:
        return Clock.model_validate(await self._get("/v2/clock"))

    async def raw_fills(self, after: str | None = None) -> list[Fill]:
        collected: list[Fill] = []
        token: str | None = None
        for _ in range(PAGES_MAX):
            page = fills_adapter.validate_python(
                await self._get(
                    "/v2/account/activities",
                    {
                        "activity_types": "FILL",
                        "direction": "desc",
                        "page_size": PAGE_ROWS_MAX,
                        "page_token": token,
                        "after": after,
                    },
                )
            )
            if not page:
                break
            collected.extend(page)
            token = page[-1].id
            if len(page) < PAGE_ROWS_MAX:
                break
        return collected

    async def raw_closed_orders(self, after: str | None = None) -> list[ClosedOrder]:
        collected: list[ClosedOrder] = []
        seen: set[str] = set()
        until: str | None = None
        for _ in range(PAGES_MAX):
            page = closed_orders_adapter.validate_python(
                await self._get(
                    "/v2/orders",
                    {
                        "status": "closed",
                        "limit": PAGE_ROWS_MAX,
                        "direction": "desc",
                        "until": until,
                        "after": after,
                    },
                )
            )
            fresh = [order for order in page if order.id not in seen]
            if not fresh:
                break
            collected.extend(fresh)
            seen.update(order.id for order in fresh)
            until = page[-1].submitted_at
            if len(page) < PAGE_ROWS_MAX:
                break
        return collected

    async def equity(self, period: str, timeframe: str) -> list[EquityPoint]:
        params: dict[str, object] = {"period": period, "timeframe": timeframe}
        if timeframe != "1D":
            params["intraday_reporting"] = "market_hours"
        history = _PortfolioHistory.model_validate(
            await self._get("/v2/account/portfolio/history", params)
        )
        return [
            EquityPoint(timestamp=timestamp, equity=equity)
            for timestamp, equity in zip(history.timestamp, history.equity, strict=True)
            if equity
        ]

    async def _get(self, path: str, params: dict[str, object] | None = None) -> Any:
        query = {key: str(value) for key, value in (params or {}).items() if value is not None}
        response = await self._client.get(path, params=query)
        response.raise_for_status()
        return response.json()


class AlpacaMarketDataClient:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def daily_bars(self, symbol: str, start: str) -> list[Bar]:
        return await self.bars(symbol, "1Day", start)

    async def bars(
        self,
        symbol: str,
        timeframe: str,
        start: str,
        end: str | None = None,
        limit: int = 1000,
    ) -> list[Bar]:
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
    ) -> list[Bar]:
        params = {
            "timeframe": timeframe,
            "start": start,
            "end": end,
            "limit": str(limit),
            "feed": "iex",
        }
        return await self._page(symbol, params, pages_max=pages_max)

    async def _page(self, symbol: str, params: dict[str, str], pages_max: int) -> list[Bar]:
        rows: list[Bar] = []
        query = dict(params)
        for _ in range(pages_max):
            response = await self._client.get(f"/v2/stocks/{symbol}/bars", params=query)
            response.raise_for_status()
            page = _BarsPage.model_validate(response.json())
            rows.extend(page.bars or [])
            if not page.next_page_token:
                break
            query = {**params, "page_token": page.next_page_token}
        return rows
