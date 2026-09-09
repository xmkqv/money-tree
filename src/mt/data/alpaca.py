from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from alpaca.common.enums import BaseURL
from alpaca.trading.models import Order
from pydantic import Field, TypeAdapter

from mt.config.sections import BrokerSection
from mt.config.values import BrokerMode, DataFeedName

from .http import Payload


class Account(Payload):
    account_number: str
    status: str
    equity: float
    last_equity: float
    cash: float
    buying_power: float


class Position(Payload):
    symbol: str
    side: str
    qty: float
    avg_entry_price: float
    current_price: float
    market_value: float
    unrealized_pl: float
    unrealized_plpc: float


class Clock(Payload):
    is_open: bool
    next_open: str
    next_close: str


class Fill(Payload):
    id: str
    order_id: str
    symbol: str
    side: str
    transaction_time: str
    qty: float
    price: float


class ClosedOrder(Payload):
    id: str
    submitted_at: str
    client_order_id: str | None = None


class Bar(Payload):
    opened_at: str = Field(alias="t")
    open: float = Field(alias="o")
    high: float = Field(alias="h")
    low: float = Field(alias="l")
    close: float = Field(alias="c")
    volume: float = Field(alias="v", default=0.0)


class EquityPoint(Payload):
    timestamp: int
    equity: float


class _PortfolioHistory(Payload):
    timestamp: list[int]
    equity: list[float | None]


class _BarsPage(Payload):
    bars: list[Bar] | None = None
    next_page_token: str | None = None


orders_adapter = TypeAdapter(list[Order])
positions_adapter = TypeAdapter(list[Position])
fills_adapter = TypeAdapter(list[Fill])
closed_orders_adapter = TypeAdapter(list[ClosedOrder])


def live_api_url(broker_mode: BrokerMode) -> str:
    target = BaseURL.TRADING_PAPER if broker_mode == "paper" else BaseURL.TRADING_LIVE
    return target.value


def past_api_url() -> str:
    return BaseURL.DATA.value


def credential_headers(broker: BrokerSection) -> dict[str, str]:
    return {
        "APCA-API-KEY-ID": broker.api_key.get_secret_value(),
        "APCA-API-SECRET-KEY": broker.api_secret.get_secret_value(),
    }


class AlpacaLiveClient:
    def __init__(self, client: httpx.AsyncClient, page_rows_max: int, pages_max: int) -> None:
        self._client = client
        self._page_rows_max = page_rows_max
        self._pages_max = pages_max

    async def account(self) -> Account:
        return Account.model_validate(await self._get("/v2/account"))

    async def positions(self) -> list[Position]:
        return positions_adapter.validate_python(await self._get("/v2/positions"))

    async def open_orders(self) -> list[Order]:
        async def read(before: str | None) -> list[Order]:
            return orders_adapter.validate_python(
                await self._get(
                    "/v2/orders",
                    {
                        "status": "open",
                        "limit": self._page_rows_max,
                        "direction": "desc",
                        "before_order_id": before,
                    },
                )
            )

        return await self._pages(read, lambda order: str(order.id))

    async def clock(self) -> Clock:
        return Clock.model_validate(await self._get("/v2/clock"))

    async def fills(self, after: str | None = None) -> list[Fill]:
        async def read(token: str | None) -> list[Fill]:
            return fills_adapter.validate_python(
                await self._get(
                    "/v2/account/activities",
                    {
                        "activity_types": "FILL",
                        "direction": "desc",
                        "page_size": self._page_rows_max,
                        "page_token": token,
                        "after": after,
                    },
                )
            )

        return await self._pages(read, lambda fill: fill.id)

    async def closed_orders(self, after: str | None = None) -> list[ClosedOrder]:
        async def read(until: str | None) -> list[ClosedOrder]:
            return closed_orders_adapter.validate_python(
                await self._get(
                    "/v2/orders",
                    {
                        "status": "closed",
                        "limit": self._page_rows_max,
                        "direction": "desc",
                        "until": until,
                        "after": after,
                    },
                )
            )

        orders = await self._pages(read, lambda order: order.submitted_at)
        return list({order.id: order for order in orders}.values())

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
            if equity is not None
        ]

    async def _pages[Row](
        self,
        read: Callable[[str | None], Awaitable[list[Row]]],
        cursor: Callable[[Row], str],
    ) -> list[Row]:
        collected: list[Row] = []
        token: str | None = None
        for _ in range(self._pages_max):
            page = await read(token)
            collected.extend(page)
            if len(page) < self._page_rows_max:
                break
            next_token = cursor(page[-1])
            if next_token == token:
                raise httpx.HTTPError("Account history pagination did not advance")
            token = next_token
        else:
            raise httpx.HTTPError("Account history exceeds the configured page limit")
        return collected

    async def _get(self, path: str, params: dict[str, object] | None = None) -> Any:
        query = {key: str(value) for key, value in (params or {}).items() if value is not None}
        response = await self._client.get(path, params=query)
        response.raise_for_status()
        return response.json()


class AlpacaPastClient:
    def __init__(
        self, client: httpx.AsyncClient, feed: DataFeedName, daily_feed: DataFeedName, bars_max: int
    ) -> None:
        self._client = client
        self._feed = feed
        self._daily_feed = daily_feed
        self._bars_max = bars_max

    async def daily_bars(self, symbol: str, start: str) -> list[Bar]:
        return await self.bars(symbol, "1Day", start)

    async def bars(
        self,
        symbol: str,
        timeframe: str,
        start: str,
        end: str | None = None,
        limit: int | None = None,
        pages_max: int = 1,
    ) -> list[Bar]:
        params = {
            "timeframe": timeframe,
            "start": start,
            "limit": str(self._bars_max if limit is None else limit),
            "feed": self._daily_feed if timeframe.endswith("Day") else self._feed,
            "adjustment": "all",
        }
        if end is not None:
            params["end"] = end
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
