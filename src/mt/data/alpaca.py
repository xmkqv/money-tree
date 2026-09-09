import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
from alpaca.common.enums import BaseURL
from alpaca.trading.models import Order
from pydantic import Field, TypeAdapter

from mt.config.sections import BarsSection, BrokerSection, DashboardSection
from mt.config.values import DataFeedName
from mt.exchange import TRADING_ZONE, upcoming_session_bounds

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
    quantity: float = Field(validation_alias="qty")
    entry: float = Field(validation_alias="avg_entry_price")
    last: float = Field(validation_alias="current_price")
    value: float = Field(validation_alias="market_value")
    unrealized_pnl: float = Field(validation_alias="unrealized_pl")
    unrealized_pnl_fraction: float = Field(validation_alias="unrealized_plpc")


class AccountObservation(Payload):
    account: Account
    positions: list[Position]
    orders: list[Order]
    observed_at: tuple[datetime, datetime, datetime]

    @property
    def read_at(self) -> datetime:
        return min(self.observed_at)


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
    quantity: float = Field(validation_alias="qty")
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


@dataclass(frozen=True)
class History:
    fills: tuple[Fill, ...]
    orders: tuple[ClosedOrder, ...]
    fill_at: datetime
    order_at: datetime
    session_at: date


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


def trading_api_url(broker: BrokerSection) -> str:
    target = BaseURL.TRADING_PAPER if broker.is_paper else BaseURL.TRADING_LIVE
    return target.value


def bars_api_url() -> str:
    return BaseURL.DATA.value


def bars_feed(timeframe: str, bars: BarsSection) -> DataFeedName:
    return bars.daily_feed if timeframe.endswith("Day") else bars.intraday_feed


def bars_end_at(end: datetime, feed: DataFeedName, sip_delay_minutes: int) -> datetime:
    if end.tzinfo is None:
        end = end.replace(tzinfo=UTC)
    if feed == "sip":
        return min(end, datetime.now(UTC) - timedelta(minutes=sip_delay_minutes))
    return end


async def get_json(
    client: httpx.AsyncClient, path: str, params: Mapping[str, object] | None = None
) -> Any:
    query = {key: str(value) for key, value in (params or {}).items() if value is not None}
    response = await client.get(path, params=query)
    response.raise_for_status()
    return response.json()


def credential_headers(broker: BrokerSection) -> dict[str, str]:
    key, secret = broker.key_pair
    return {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}


class TradingClientAlpaca:
    def __init__(self, client: httpx.AsyncClient, configuration: DashboardSection) -> None:
        self._client = client
        self._configuration = configuration
        self._page_rows_max = configuration.page_rows_max
        self._pages_max = configuration.pages_max
        self._history: History | None = None
        self._history_lock = asyncio.Lock()
        self._daily: tuple[date, list[EquityPoint]] | None = None
        self._daily_lock = asyncio.Lock()

    async def observation(self) -> AccountObservation:
        async def observe[Value](read: Awaitable[Value]) -> tuple[Value, datetime]:
            return await read, datetime.now(UTC)

        async with asyncio.TaskGroup() as reads:
            account = reads.create_task(observe(self.account()))
            positions = reads.create_task(observe(self.positions()))
            orders = reads.create_task(observe(self.open_orders()))
        return AccountObservation(
            account=account.result()[0],
            positions=positions.result()[0],
            orders=orders.result()[0],
            observed_at=(account.result()[1], positions.result()[1], orders.result()[1]),
        )

    async def history(self) -> History:
        async with self._history_lock:
            now = datetime.now(UTC)
            session = upcoming_session_bounds(now.astimezone(TRADING_ZONE).date())[0].date()
            prior = self._history
            if prior is not None and prior.session_at != session:
                prior = None
            overlap = timedelta(days=self._configuration.history_overlap_days)
            async with asyncio.TaskGroup() as reads:
                fills_read = reads.create_task(
                    self.fills((prior.fill_at - overlap).isoformat() if prior else None)
                )
                orders_read = reads.create_task(
                    self.closed_orders((prior.order_at - overlap).isoformat() if prior else None)
                )
            fills = {row.id: row for row in prior.fills} if prior else {}
            orders = {row.id: row for row in prior.orders} if prior else {}
            fills.update((row.id, row) for row in fills_read.result())
            orders.update((row.id, row) for row in orders_read.result())
            async with asyncio.TaskGroup() as reads:
                missing = {
                    order_id: reads.create_task(self._get(f"/v2/orders/{order_id}"))
                    for order_id in {row.order_id for row in fills.values()} - orders.keys()
                }
            orders.update(
                (key, ClosedOrder.model_validate(read.result())) for key, read in missing.items()
            )
            self._history = History(
                tuple(fills.values()),
                tuple(orders.values()),
                max(
                    (datetime.fromisoformat(row.transaction_time) for row in fills.values()),
                    default=now,
                ),
                max(
                    (datetime.fromisoformat(row.submitted_at) for row in orders.values()),
                    default=now,
                ),
                session,
            )
            return self._history

    async def daily_equity(self) -> list[EquityPoint]:
        async with self._daily_lock:
            today = datetime.now(TRADING_ZONE).date()
            session = upcoming_session_bounds(today)[0].date()
            if self._daily is None or self._daily[0] != session:
                points = await self.equity(
                    self._configuration.equity_daily_period,
                    self._configuration.equity_daily_timeframe,
                )
                self._daily = (
                    session,
                    [
                        point
                        for point in points
                        if datetime.fromtimestamp(point.timestamp, TRADING_ZONE).date() < today
                    ],
                )
            return self._daily[1]

    async def account(self) -> Account:
        return Account.model_validate(await self._get("/v2/account"))

    async def positions(self) -> list[Position]:
        return positions_adapter.validate_python(await self._get("/v2/positions"))

    async def open_orders(self) -> list[Order]:
        return await self._pages(
            "/v2/orders",
            orders_adapter,
            lambda order: str(order.id),
            "before_order_id",
            status="open",
            limit=self._page_rows_max,
        )

    async def clock(self) -> Clock:
        return Clock.model_validate(await self._get("/v2/clock"))

    async def fills(self, after: str | None = None) -> list[Fill]:
        return await self._pages(
            "/v2/account/activities",
            fills_adapter,
            lambda fill: fill.id,
            "page_token",
            activity_types="FILL",
            page_size=self._page_rows_max,
            after=after,
        )

    async def closed_orders(self, after: str | None = None) -> list[ClosedOrder]:
        orders = await self._pages(
            "/v2/orders",
            closed_orders_adapter,
            lambda order: order.submitted_at,
            "until",
            status="closed",
            limit=self._page_rows_max,
            after=after,
        )
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
        path: str,
        adapter: TypeAdapter[list[Row]],
        cursor: Callable[[Row], str],
        token_name: str,
        **params: object,
    ) -> list[Row]:
        collected: list[Row] = []
        token: str | None = None
        for _ in range(self._pages_max):
            page = adapter.validate_python(
                await self._get(path, {**params, "direction": "desc", token_name: token})
            )
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
        return await get_json(self._client, path, params)


class BarsClientAlpaca:
    def __init__(
        self, client: httpx.AsyncClient, configuration: BarsSection, bars_max: int
    ) -> None:
        self._client = client
        self._configuration = configuration
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
        feed = bars_feed(timeframe, self._configuration)
        params = {
            "timeframe": timeframe,
            "start": start,
            "limit": str(self._bars_max if limit is None else limit),
            "feed": feed,
            "adjustment": "all",
        }
        if end is not None:
            params["end"] = bars_end_at(
                datetime.fromisoformat(end), feed, self._configuration.sip_delay_minutes
            ).isoformat()
        return await self._page(symbol, params, pages_max=pages_max)

    async def _page(self, symbol: str, params: dict[str, str], pages_max: int) -> list[Bar]:
        rows: list[Bar] = []
        query = dict(params)
        for _ in range(pages_max):
            page = _BarsPage.model_validate(
                await get_json(self._client, f"/v2/stocks/{symbol}/bars", query)
            )
            rows.extend(page.bars or [])
            if not page.next_page_token:
                break
            query = {**params, "page_token": page.next_page_token}
        return rows
