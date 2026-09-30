import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from http import HTTPStatus
from typing import Annotated, Literal

import httpx2
from alpaca.trading.models import Asset as BrokerAssetProfile
from alpaca.trading.models import Clock, Order
from pydantic import AwareDatetime, BeforeValidator, Field, TypeAdapter

from mt.exchange import today_on, upcoming_session_on
from mt.rules.sections import BrokerSection, DashboardSection
from mt.sizing import Direction

from .http import ExceedPagesError, Payload, get_bytes


class Account(Payload):
    account_number: str
    equity: float
    cash: float
    buying_power: float


class Position(Payload):
    symbol: str
    side: Literal["long", "short"]
    quantity: float = Field(validation_alias="qty")
    entry: float = Field(validation_alias="avg_entry_price")
    last: float = Field(validation_alias="current_price")
    value: float = Field(validation_alias="market_value")
    unrealized_pnl: float = Field(validation_alias="unrealized_pl")
    unrealized_pnl_fraction: float = Field(validation_alias="unrealized_plpc")


class AccountRead(Payload):
    account: Account
    positions: list[Position]
    orders: list[Order]
    read_at: AwareDatetime


FILL_DIRECTIONS: dict[str, Direction] = {"buy": 1, "sell": -1, "sell_short": -1}


def _direction(side: str) -> Direction:
    if side not in FILL_DIRECTIONS:
        raise ValueError(f"fill side {side!r} is unknown")
    return FILL_DIRECTIONS[side]


class Fill(Payload):
    id: str
    order_id: str
    symbol: str
    direction: Annotated[Direction, BeforeValidator(_direction)] = Field(validation_alias="side")
    transaction_time: AwareDatetime
    quantity: float = Field(validation_alias="qty")
    price: float


class EquityPoint(Payload):
    recorded_at: AwareDatetime = Field(validation_alias="timestamp")
    equity: float


@dataclass(frozen=True)
class History:
    fills: tuple[Fill, ...]
    orders: tuple[Order, ...]
    last_fill_at: datetime
    last_order_at: datetime
    session_on: date


class _PortfolioHistory(Payload):
    timestamp: list[AwareDatetime]
    equity: list[float | None]


_orders_adapter = TypeAdapter(list[Order])
_positions_adapter = TypeAdapter(list[Position])
_fills_adapter = TypeAdapter(list[Fill])


def credential_headers(broker: BrokerSection) -> dict[str, str]:
    key, secret = broker.key_pair
    return {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}


class TradingClientAlpaca:
    def __init__(self, client: httpx2.AsyncClient, configuration: DashboardSection) -> None:
        self._client = client
        self._configuration = configuration
        self._history: History | None = None
        self._history_lock = asyncio.Lock()

    async def read(self) -> AccountRead:
        read_at = datetime.now(UTC)
        async with asyncio.TaskGroup() as reads:
            account = reads.create_task(self._account())
            positions = reads.create_task(self._positions())
            orders = reads.create_task(self._orders("open"))
        return AccountRead(
            account=account.result(),
            positions=positions.result(),
            orders=orders.result(),
            read_at=read_at,
        )

    async def history(self) -> History:
        async with self._history_lock:
            now = datetime.now(UTC)
            session_on = upcoming_session_on(today_on())
            prior = (
                self._history
                if self._history is not None and self._history.session_on == session_on
                else None
            )
            overlap = timedelta(days=self._configuration.history_overlap_days)
            async with asyncio.TaskGroup() as reads:
                fills_read = reads.create_task(
                    self._fills(prior.last_fill_at - overlap if prior else None)
                )
                orders_read = reads.create_task(
                    self._orders("closed", prior.last_order_at - overlap if prior else None)
                )
            fills = {row.id: row for row in prior.fills} if prior else {}
            orders = {str(row.id): row for row in prior.orders} if prior else {}
            fills.update((row.id, row) for row in fills_read.result())
            orders.update((str(row.id), row) for row in orders_read.result())
            async with asyncio.TaskGroup() as reads:
                missing = {
                    order_id: reads.create_task(get_bytes(self._client, f"/v2/orders/{order_id}"))
                    for order_id in {row.order_id for row in fills.values()} - orders.keys()
                }
            orders.update(
                (key, Order.model_validate_json(read.result())) for key, read in missing.items()
            )
            self._history = History(
                tuple(fills.values()),
                tuple(orders.values()),
                max((row.transaction_time for row in fills.values()), default=now),
                max((row.submitted_at for row in orders.values()), default=now),
                session_on,
            )
            return self._history

    async def clock(self) -> Clock:
        return Clock.model_validate_json(await get_bytes(self._client, "/v2/clock"))

    async def asset_name(self, symbol: str) -> str | None:
        try:
            payload = await get_bytes(self._client, f"/v2/assets/{symbol}")
        except httpx2.HTTPStatusError as error:
            if error.response.status_code != HTTPStatus.NOT_FOUND:
                raise
            return None
        return BrokerAssetProfile.model_validate_json(payload).name

    async def equity(self, period: str, timeframe: str) -> list[EquityPoint]:
        params: dict[str, object] = {"period": period, "timeframe": timeframe}
        if timeframe != "1D":
            params["intraday_reporting"] = "market_hours"
        history = _PortfolioHistory.model_validate_json(
            await get_bytes(self._client, "/v2/account/portfolio/history", params)
        )
        return [
            EquityPoint(recorded_at=recorded_at, equity=equity)
            for recorded_at, equity in zip(history.timestamp, history.equity, strict=True)
            if equity is not None
        ]

    async def _account(self) -> Account:
        return Account.model_validate_json(await get_bytes(self._client, "/v2/account"))

    async def _positions(self) -> list[Position]:
        return _positions_adapter.validate_json(await get_bytes(self._client, "/v2/positions"))

    async def _orders(
        self, status: Literal["open", "closed"], after_at: datetime | None = None
    ) -> list[Order]:
        return await self._pages(
            "/v2/orders",
            _orders_adapter,
            _submitted_cursor,
            "until",
            status=status,
            limit=self._configuration.page_rows_max,
            after=after_at,
        )

    async def _fills(self, after_at: datetime | None) -> list[Fill]:
        return await self._pages(
            "/v2/account/activities",
            _fills_adapter,
            lambda fill: fill.id,
            "page_token",
            activity_types="FILL",
            page_size=self._configuration.page_rows_max,
            after=after_at,
        )

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
        for _ in range(self._configuration.pages_max):
            page = adapter.validate_json(
                await get_bytes(
                    self._client, path, {**params, "direction": "desc", token_name: token}
                )
            )
            collected.extend(page)
            if len(page) < self._configuration.page_rows_max:
                break
            next_token = cursor(page[-1])
            if next_token == token:
                raise ExceedPagesError("Pagination did not advance")
            token = next_token
        else:
            raise ExceedPagesError("Pages exceed the configured page limit")
        return collected


def _submitted_cursor(order: Order) -> str:
    return order.submitted_at.isoformat()
