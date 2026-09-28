from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime, timedelta
from functools import partial

import httpx2
from anyio.from_thread import BlockingPortal, start_blocking_portal
from pandas import DataFrame

from mt.data.alpaca import credential_headers
from mt.data.asset import Asset
from mt.data.bars import BarsClientAlpaca, Trade, bar_frame, bars_api_url
from mt.data.http import http_timeout
from mt.exchange import trading_time
from mt.rules.shared import settings
from mt.rules.values import Timeframe


class Bars:
    def __init__(self, portal: BlockingPortal) -> None:
        self._portal = portal
        self._http: httpx2.AsyncClient | None = None
        self._client: BarsClientAlpaca | None = None

    def bars(
        self, assets: list[Asset], timeframe: Timeframe, start: datetime, end: datetime
    ) -> dict[Asset, DataFrame]:
        return self._portal.call(partial(self._frames, assets, timeframe, start, end))

    def prices(self, assets: list[Asset], now: datetime) -> dict[Asset, float]:
        trades = self._portal.call(partial(self._trades, assets))
        oldest = now - timedelta(seconds=settings.bars.trade_max_age_seconds)
        return {
            asset: trade.price
            for asset, trade in trades.items()
            if trading_time(trade.traded_at) >= oldest and trade.price > 0
        }

    def _connected(self) -> BarsClientAlpaca:
        if self._client is None:
            self._http = httpx2.AsyncClient(
                base_url=bars_api_url(),
                headers=credential_headers(settings.broker),
                timeout=http_timeout(settings.bars.timeout),
            )
            self._client = BarsClientAlpaca(self._http, settings.bars)
        return self._client

    async def _frames(
        self, assets: list[Asset], timeframe: Timeframe, start: datetime, end: datetime
    ) -> dict[Asset, DataFrame]:
        rows = await self._connected().bars(
            assets, timeframe, start, end, limit=settings.bars.bars_per_request
        )
        return {asset: bar_frame(bars) for asset, bars in rows.items() if bars}

    async def _trades(self, assets: list[Asset]) -> dict[Asset, Trade]:
        return await self._connected().latest_trades(assets)

    async def aclose(self) -> None:
        if self._http is not None:
            await self._http.aclose()


@contextmanager
def bars_client() -> Generator[Bars]:
    with start_blocking_portal() as portal:
        bars = Bars(portal)
        try:
            yield bars
        finally:
            portal.call(bars.aclose)
